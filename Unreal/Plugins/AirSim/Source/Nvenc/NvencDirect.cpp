#include "NvencDirect.h"

#if PLATFORM_WINDOWS
THIRD_PARTY_INCLUDES_START
#include "Windows/AllowWindowsPlatformTypes.h"
#include <d3d11.h>
#include "Windows/HideWindowsPlatformTypes.h"
#include "nvEncodeAPI.h"
THIRD_PARTY_INCLUDES_END
#include "RHI.h"
#endif

namespace
{
#if PLATFORM_WINDOWS
    struct FGlobalNvencState
    {
        HMODULE DllHandle = nullptr;
        NV_ENCODE_API_FUNCTION_LIST Api = { NV_ENCODE_API_FUNCTION_LIST_VER };
        bool bApiLoaded = false;
        FCriticalSection EncodeApiMutex;
    };

    FGlobalNvencState& Global()
    {
        static FGlobalNvencState State;
        return State;
    }

    static int32 AlignEven(int32 Value)
    {
        return Value & ~1;
    }

    static NV_ENC_BUFFER_FORMAT PickBufferFormat(const FNvencConfig& Config)
    {
        return NV_ENC_BUFFER_FORMAT_ARGB;
    }

    static GUID PickCodecGuid(const FNvencConfig& Config)
    {
        if (Config.EncodeMode == msr::airlib::EncodedImageCaptureBase::EncodeMode::NvencHevc)
            return NV_ENC_CODEC_HEVC_GUID;
        return NV_ENC_CODEC_H264_GUID;
    }

    static GUID PickPresetGuid(const FNvencConfig& Config)
    {
        if (Config.bLossless)
            return NV_ENC_PRESET_P7_GUID;
        return NV_ENC_PRESET_P4_GUID;
    }

    static NV_ENC_TUNING_INFO PickTuningInfo(const FNvencConfig& Config)
    {
        if (Config.bLossless)
            return NV_ENC_TUNING_INFO_LOSSLESS;
        return NV_ENC_TUNING_INFO_HIGH_QUALITY;
    }
#endif
} // namespace

FNvencEncoder::FNvencEncoder() = default;

FNvencEncoder::~FNvencEncoder()
{
    Shutdown();
}

bool FNvencDirect::IsPlatformSupported()
{
#if PLATFORM_WINDOWS
    return true;
#else
    return false;
#endif
}

bool FNvencEncoder::IsAvailable()
{
#if PLATFORM_WINDOWS
    FString Error;
    return EnsureApiLoaded(Error);
#else
    return false;
#endif
}

bool FNvencEncoder::EnsureApiLoaded(FString& OutError)
{
#if PLATFORM_WINDOWS
    FScopeLock Lock(&Global().EncodeApiMutex);
    if (Global().bApiLoaded)
        return true;

    if (!Global().DllHandle) {
        Global().DllHandle = LoadLibraryW(L"nvEncodeAPI64.dll");
        if (!Global().DllHandle) {
            OutError = TEXT("Failed to load nvEncodeAPI64.dll");
            return false;
        }
    }

    using NvEncodeAPICreateInstanceFn = NVENCSTATUS(NVENCAPI*)(NV_ENCODE_API_FUNCTION_LIST*);
    auto CreateInstance = reinterpret_cast<NvEncodeAPICreateInstanceFn>(GetProcAddress(Global().DllHandle, "NvEncodeAPICreateInstance"));
    if (!CreateInstance) {
        OutError = TEXT("NvEncodeAPICreateInstance not found");
        return false;
    }

    Global().Api = { NV_ENCODE_API_FUNCTION_LIST_VER };
    const NVENCSTATUS Status = CreateInstance(&Global().Api);
    if (Status != NV_ENC_SUCCESS) {
        OutError = FString::Printf(TEXT("NvEncodeAPICreateInstance failed: %d"), Status);
        return false;
    }

    Global().bApiLoaded = true;
    return true;
#else
    OutError = TEXT("NVENC is only supported on Windows");
    return false;
#endif
}

bool FNvencEncoder::Init(const FNvencConfig& Config, FString& OutError)
{
#if PLATFORM_WINDOWS
    if (bInitialized_)
        Shutdown();

    if (!EnsureApiLoaded(OutError))
        return false;

    ActiveConfig_ = Config;
    EncWidth_ = AlignEven(Config.Width);
    EncHeight_ = AlignEven(Config.Height);
    if (EncWidth_ <= 0 || EncHeight_ <= 0) {
        OutError = TEXT("Invalid encoder dimensions");
        return false;
    }

    return CreateSession(Config, OutError);
#else
    OutError = TEXT("NVENC unavailable on this platform");
    return false;
#endif
}

bool FNvencEncoder::CreateSession(const FNvencConfig& Config, FString& OutError)
{
#if PLATFORM_WINDOWS
    FScopeLock Lock(&Global().EncodeApiMutex);

    if (!GDynamicRHI) {
        OutError = TEXT("GDynamicRHI is null");
        return false;
    }

    void* DxDevice = GDynamicRHI->RHIGetNativeDevice();
    if (!DxDevice) {
        OutError = TEXT("DirectX device unavailable");
        return false;
    }

    NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS OpenParams = { NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER };
    OpenParams.device = DxDevice;
    OpenParams.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
    OpenParams.apiVersion = NVENCAPI_VERSION;

    void* Encoder = nullptr;
    NVENCSTATUS Status = Global().Api.nvEncOpenEncodeSessionEx(&OpenParams, &Encoder);
    if (Status != NV_ENC_SUCCESS || !Encoder) {
        OutError = FString::Printf(TEXT("nvEncOpenEncodeSessionEx failed: %d"), Status);
        return false;
    }
    EncoderHandle_ = Encoder;

    const GUID CodecGuid = PickCodecGuid(Config);
    const GUID PresetGuid = PickPresetGuid(Config);
    const NV_ENC_TUNING_INFO TuningInfo = PickTuningInfo(Config);

    NV_ENC_PRESET_CONFIG PresetConfig = { NV_ENC_PRESET_CONFIG_VER, 0, { NV_ENC_CONFIG_VER } };
    Status = Global().Api.nvEncGetEncodePresetConfigEx(EncoderHandle_, CodecGuid, PresetGuid, TuningInfo, &PresetConfig);
    if (Status != NV_ENC_SUCCESS) {
        OutError = FString::Printf(TEXT("nvEncGetEncodePresetConfigEx failed: %d"), Status);
        DestroySession();
        return false;
    }

    NV_ENC_INITIALIZE_PARAMS InitParams = { NV_ENC_INITIALIZE_PARAMS_VER };
    NV_ENC_CONFIG EncodeConfig = PresetConfig.presetCfg;
    InitParams.encodeWidth = EncWidth_;
    InitParams.encodeHeight = EncHeight_;
    InitParams.darWidth = EncWidth_;
    InitParams.darHeight = EncHeight_;
    InitParams.frameRateNum = 30;
    InitParams.frameRateDen = 1;
    InitParams.enablePTD = 1;
    InitParams.reportSliceOffsets = 0;
    InitParams.enableSubFrameWrite = 0;
    InitParams.enableEncodeAsync = 0;
    InitParams.encodeGUID = CodecGuid;
    InitParams.presetGUID = PresetGuid;
    InitParams.tuningInfo = TuningInfo;
    InitParams.encodeConfig = &EncodeConfig;

    EncodeConfig.version = NV_ENC_CONFIG_VER;
    EncodeConfig.gopLength = FMath::Max(1, Config.GopSize);
    EncodeConfig.frameIntervalP = 1;
    EncodeConfig.rcParams.version = NV_ENC_RC_PARAMS_VER;
    EncodeConfig.rcParams.rateControlMode = NV_ENC_PARAMS_RC_CONSTQP;
    if (Config.bLossless) {
        EncodeConfig.rcParams.constQP.qpIntra = 0;
        EncodeConfig.rcParams.constQP.qpInterP = 0;
        EncodeConfig.rcParams.constQP.qpInterB = 0;
    }
    else {
        EncodeConfig.rcParams.constQP.qpIntra = Config.CqOrQp;
        EncodeConfig.rcParams.constQP.qpInterP = Config.CqOrQp;
        EncodeConfig.rcParams.constQP.qpInterB = Config.CqOrQp;
    }

    if (Config.EncodeMode == msr::airlib::EncodedImageCaptureBase::EncodeMode::NvencHevc) {
        auto& Hevc = EncodeConfig.encodeCodecConfig.hevcConfig;
        Hevc.chromaFormatIDC = (Config.PixFmt == msr::airlib::EncodedImageCaptureBase::EncodedPixFmt::Yuv420) ? 1 : 3;
        if (Config.bLossless) {
            InitParams.tuningInfo = NV_ENC_TUNING_INFO_LOSSLESS;
        }
        if (Config.PixFmt != msr::airlib::EncodedImageCaptureBase::EncodedPixFmt::Yuv420) {
            EncodeConfig.profileGUID = NV_ENC_HEVC_PROFILE_FREXT_GUID;
            auto& Vui = Hevc.hevcVUIParameters;
            Vui.colourMatrix = NV_ENC_VUI_MATRIX_COEFFS_RGB;
            Vui.transferCharacteristics = NV_ENC_VUI_TRANSFER_CHARACTERISTIC_LINEAR;
            Vui.colourPrimaries = NV_ENC_VUI_COLOR_PRIMARIES_BT709;
            Vui.videoFullRangeFlag = 1;
        }
    }

    Status = Global().Api.nvEncInitializeEncoder(EncoderHandle_, &InitParams);
    if (Status != NV_ENC_SUCCESS) {
        OutError = FString::Printf(TEXT("nvEncInitializeEncoder failed: %d"), Status);
        DestroySession();
        return false;
    }

    NV_ENC_CREATE_BITSTREAM_BUFFER CreateBitstream = { NV_ENC_CREATE_BITSTREAM_BUFFER_VER };
    Status = Global().Api.nvEncCreateBitstreamBuffer(EncoderHandle_, &CreateBitstream);
    if (Status != NV_ENC_SUCCESS) {
        OutError = FString::Printf(TEXT("nvEncCreateBitstreamBuffer failed: %d"), Status);
        DestroySession();
        return false;
    }
    BitstreamBuffer_ = CreateBitstream.bitstreamBuffer;

    NV_ENC_CREATE_INPUT_BUFFER CreateInput = { NV_ENC_CREATE_INPUT_BUFFER_VER };
    CreateInput.width = EncWidth_;
    CreateInput.height = EncHeight_;
    CreateInput.bufferFmt = PickBufferFormat(Config);
    Status = Global().Api.nvEncCreateInputBuffer(EncoderHandle_, &CreateInput);
    if (Status != NV_ENC_SUCCESS) {
        OutError = FString::Printf(TEXT("nvEncCreateInputBuffer failed: %d"), Status);
        DestroySession();
        return false;
    }
    InputBuffer_ = CreateInput.inputBuffer;

    bInitialized_ = true;
    return true;
#else
    OutError = TEXT("NVENC unavailable");
    return false;
#endif
}

void FNvencEncoder::DestroySession()
{
#if PLATFORM_WINDOWS
    FScopeLock Lock(&Global().EncodeApiMutex);
    if (!Global().bApiLoaded || !EncoderHandle_)
        return;

    if (BitstreamBuffer_) {
        Global().Api.nvEncDestroyBitstreamBuffer(EncoderHandle_, BitstreamBuffer_);
        BitstreamBuffer_ = nullptr;
    }
    if (InputBuffer_) {
        Global().Api.nvEncDestroyInputBuffer(EncoderHandle_, InputBuffer_);
        InputBuffer_ = nullptr;
    }
    Global().Api.nvEncDestroyEncoder(EncoderHandle_);
    EncoderHandle_ = nullptr;
    bInitialized_ = false;
#endif
}

void FNvencEncoder::Shutdown()
{
    DestroySession();
}

bool FNvencEncoder::EncodeBGRA(const TArray<FColor>& BgraSrc, int32 SrcWidth, int32 SrcHeight, FEncodedFrame& OutFrame)
{
#if PLATFORM_WINDOWS
    if (!bInitialized_) {
        OutFrame.Error = TEXT("Encoder not initialized");
        return false;
    }

    FScopeLock Lock(&Global().EncodeApiMutex);

    NV_ENC_LOCK_INPUT_BUFFER LockInput = { NV_ENC_LOCK_INPUT_BUFFER_VER };
    LockInput.inputBuffer = InputBuffer_;
    NVENCSTATUS Status = Global().Api.nvEncLockInputBuffer(EncoderHandle_, &LockInput);
    if (Status != NV_ENC_SUCCESS) {
        OutFrame.Error = FString::Printf(TEXT("nvEncLockInputBuffer failed: %d"), Status);
        return false;
    }

    const int32 DstPitch = static_cast<int32>(LockInput.pitch);
    uint8* Dst = static_cast<uint8*>(LockInput.bufferDataPtr);
    const int32 CopyWidth = FMath::Min(SrcWidth, EncWidth_);
    const int32 CopyHeight = FMath::Min(SrcHeight, EncHeight_);

    for (int32 Row = 0; Row < CopyHeight; ++Row) {
        const FColor* SrcRow = BgraSrc.GetData() + Row * SrcWidth;
        uint8* DstRow = Dst + Row * DstPitch;
        for (int32 Col = 0; Col < CopyWidth; ++Col) {
            DstRow[Col * 4 + 0] = SrcRow[Col].B;
            DstRow[Col * 4 + 1] = SrcRow[Col].G;
            DstRow[Col * 4 + 2] = SrcRow[Col].R;
            DstRow[Col * 4 + 3] = 255;
        }
    }

    Status = Global().Api.nvEncUnlockInputBuffer(EncoderHandle_, InputBuffer_);
    if (Status != NV_ENC_SUCCESS) {
        OutFrame.Error = FString::Printf(TEXT("nvEncUnlockInputBuffer failed: %d"), Status);
        return false;
    }

    NV_ENC_PIC_PARAMS PicParams = { NV_ENC_PIC_PARAMS_VER };
    PicParams.inputBuffer = InputBuffer_;
    PicParams.bufferFmt = PickBufferFormat(ActiveConfig_);
    PicParams.inputWidth = EncWidth_;
    PicParams.inputHeight = EncHeight_;
    PicParams.outputBitstream = BitstreamBuffer_;
    PicParams.pictureStruct = NV_ENC_PIC_STRUCT_FRAME;
    PicParams.inputTimeStamp = 0;
    if (ActiveConfig_.GopSize <= 1)
        PicParams.encodePicFlags = NV_ENC_PIC_FLAG_FORCEIDR;

    Status = Global().Api.nvEncEncodePicture(EncoderHandle_, &PicParams);
    if (Status != NV_ENC_SUCCESS && Status != NV_ENC_ERR_NEED_MORE_INPUT) {
        OutFrame.Error = FString::Printf(TEXT("nvEncEncodePicture failed: %d"), Status);
        return false;
    }

    NV_ENC_LOCK_BITSTREAM LockBitstream = { NV_ENC_LOCK_BITSTREAM_VER };
    LockBitstream.outputBitstream = BitstreamBuffer_;
    LockBitstream.doNotWait = 0;
    Status = Global().Api.nvEncLockBitstream(EncoderHandle_, &LockBitstream);
    if (Status != NV_ENC_SUCCESS) {
        OutFrame.Error = FString::Printf(TEXT("nvEncLockBitstream failed: %d"), Status);
        return false;
    }

    OutFrame.Bitstream.SetNumUninitialized(LockBitstream.bitstreamSizeInBytes);
    FMemory::Memcpy(OutFrame.Bitstream.GetData(), LockBitstream.bitstreamBufferPtr, LockBitstream.bitstreamSizeInBytes);
    OutFrame.Width = EncWidth_;
    OutFrame.Height = EncHeight_;

    Global().Api.nvEncUnlockBitstream(EncoderHandle_, BitstreamBuffer_);
    return true;
#else
    OutFrame.Error = TEXT("NVENC unavailable");
    return false;
#endif
}

FNvencDirect& FNvencDirect::Get()
{
    static FNvencDirect Instance;
    return Instance;
}

bool FNvencDirect::EncodeBGRA(const FNvencConfig& Config, const TArray<FColor>& BgraSrc, int32 SrcWidth, int32 SrcHeight, FEncodedFrame& OutFrame)
{
#if PLATFORM_WINDOWS
    FNvencEncoder Encoder;
    FString Error;
    if (!Encoder.Init(Config, Error)) {
        OutFrame.Error = Error;
        return false;
    }
    return Encoder.EncodeBGRA(BgraSrc, SrcWidth, SrcHeight, OutFrame);
#else
    OutFrame.Error = TEXT("NVENC unavailable");
    return false;
#endif
}
