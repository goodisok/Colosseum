#include "EncodedImagePipeline.h"

FEncodedImagePipeline& FEncodedImagePipeline::Get()
{
    static FEncodedImagePipeline Instance;
    return Instance;
}

TSharedPtr<FNvencEncoder> FEncodedImagePipeline::GetOrCreateSession(const FEncoderSessionKey& Key, const FNvencConfig& Config, FString& OutError)
{
    FScopeLock Lock(&CacheMutex_);
    if (TSharedPtr<FNvencEncoder>* Found = SessionCache_.Find(Key)) {
        return *Found;
    }

    TSharedPtr<FNvencEncoder> NewSession = MakeShared<FNvencEncoder>();
    if (!NewSession->Init(Config, OutError))
        return nullptr;

    SessionCache_.Add(Key, NewSession);
    return NewSession;
}

bool FEncodedImagePipeline::EncodeRequest(const msr::airlib::EncodedImageCaptureBase::EncodedImageRequest& Request,
                                          const TArray<FColor>& BgraSrc, int32 SrcWidth, int32 SrcHeight, FEncodedFrame& OutFrame)
{
    if (!FNvencDirect::IsPlatformSupported()) {
        OutFrame.Error = TEXT("NVENC unavailable");
        return false;
    }

    FNvencConfig Config;
    Config.Width = SrcWidth;
    Config.Height = SrcHeight;
    Config.EncodeMode = Request.encode_mode;
    Config.PixFmt = Request.pix_fmt;
    Config.bLossless = Request.lossless;
    Config.CqOrQp = Request.cq_or_qp;
    Config.GopSize = Request.gop_size;

    FEncoderSessionKey Key;
    Key.CameraName = UTF8_TO_TCHAR(Request.camera_name.c_str());
    Key.EncodeMode = Request.encode_mode;
    Key.Width = SrcWidth & ~1;
    Key.Height = SrcHeight & ~1;
    Key.PixFmt = Request.pix_fmt;

    FString Error;
    TSharedPtr<FNvencEncoder> Session = GetOrCreateSession(Key, Config, Error);
    if (!Session.IsValid()) {
        OutFrame.Error = Error;
        return false;
    }

    return Session->EncodeBGRA(BgraSrc, SrcWidth, SrcHeight, OutFrame);
}
