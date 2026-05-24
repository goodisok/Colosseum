#pragma once

#include "CoreMinimal.h"
#include "common/EncodedImageCaptureBase.hpp"

struct FEncodedFrame
{
    TArray<uint8> Bitstream;
    int32 Width = 0;
    int32 Height = 0;
    FString Error;
};

struct FNvencConfig
{
    int32 Width = 0;
    int32 Height = 0;
    msr::airlib::EncodedImageCaptureBase::EncodeMode EncodeMode = msr::airlib::EncodedImageCaptureBase::EncodeMode::NvencH264;
    msr::airlib::EncodedImageCaptureBase::EncodedPixFmt PixFmt = msr::airlib::EncodedImageCaptureBase::EncodedPixFmt::Yuv420;
    bool bLossless = false;
    int32 CqOrQp = 23;
    int32 GopSize = 1;
};

class FNvencEncoder
{
public:
    FNvencEncoder();
    ~FNvencEncoder();

    bool Init(const FNvencConfig& Config, FString& OutError);
    bool EncodeBGRA(const TArray<FColor>& BgraSrc, int32 SrcWidth, int32 SrcHeight, FEncodedFrame& OutFrame);
    void Shutdown();

    bool IsAvailable();

private:
    bool EnsureApiLoaded(FString& OutError);
    bool CreateSession(const FNvencConfig& Config, FString& OutError);
    void DestroySession();

    FNvencConfig ActiveConfig_;
    bool bInitialized_ = false;

    void* EncoderHandle_ = nullptr;
    void* InputBuffer_ = nullptr;
    void* BitstreamBuffer_ = nullptr;
    int32 EncWidth_ = 0;
    int32 EncHeight_ = 0;
};

class FNvencDirect
{
public:
    static FNvencDirect& Get();
    static bool IsPlatformSupported();

    bool EncodeBGRA(const FNvencConfig& Config, const TArray<FColor>& BgraSrc, int32 SrcWidth, int32 SrcHeight, FEncodedFrame& OutFrame);

private:
    FNvencDirect() = default;
    FCriticalSection SessionMutex_;
};
