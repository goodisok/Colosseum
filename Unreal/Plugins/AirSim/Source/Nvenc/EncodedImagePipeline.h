#pragma once

#include "NvencDirect.h"
#include "common/EncodedImageCaptureBase.hpp"

struct FEncoderSessionKey
{
    FString CameraName;
    msr::airlib::EncodedImageCaptureBase::EncodeMode EncodeMode;
    int32 Width = 0;
    int32 Height = 0;
    msr::airlib::EncodedImageCaptureBase::EncodedPixFmt PixFmt;

    bool operator==(const FEncoderSessionKey& Other) const
    {
        return CameraName == Other.CameraName && EncodeMode == Other.EncodeMode && Width == Other.Width &&
               Height == Other.Height && PixFmt == Other.PixFmt;
    }
};

FORCEINLINE uint32 GetTypeHash(const FEncoderSessionKey& Key)
{
    return HashCombine(HashCombine(GetTypeHash(Key.CameraName), static_cast<uint32>(Key.EncodeMode)),
                       HashCombine(HashCombine(static_cast<uint32>(Key.Width), static_cast<uint32>(Key.Height)),
                                   static_cast<uint32>(Key.PixFmt)));
}

class FEncodedImagePipeline
{
public:
    static FEncodedImagePipeline& Get();

    bool EncodeRequest(const msr::airlib::EncodedImageCaptureBase::EncodedImageRequest& Request,
                       const TArray<FColor>& BgraSrc, int32 SrcWidth, int32 SrcHeight, FEncodedFrame& OutFrame);

private:
    TSharedPtr<FNvencEncoder> GetOrCreateSession(const FEncoderSessionKey& Key, const FNvencConfig& Config, FString& OutError);

    TMap<FEncoderSessionKey, TSharedPtr<FNvencEncoder>> SessionCache_;
    FCriticalSection CacheMutex_;
};
