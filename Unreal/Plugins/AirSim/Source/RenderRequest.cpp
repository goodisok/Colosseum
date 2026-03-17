#include "RenderRequest.h"
#include "TextureResource.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Async/TaskGraphInterfaces.h"
#include "ImageUtils.h"

#include "AirBlueprintLib.h"
#include "Async/Async.h"

RenderRequest::RenderRequest(UGameViewportClient* game_viewport, std::function<void()>&& query_camera_pose_cb)
    : params_(nullptr), results_(nullptr), req_size_(0), wait_signal_(new msr::airlib::WorkerThreadSignal), game_viewport_(game_viewport), query_camera_pose_cb_(std::move(query_camera_pose_cb))
{
}

RenderRequest::~RenderRequest()
{
}

// read pixels from render target using render thread, then compress the result into PNG
// argument on the thread that calls this method.
void RenderRequest::getScreenshot(std::shared_ptr<RenderParams> params[], std::vector<std::shared_ptr<RenderResult>>& results, unsigned int req_size, bool use_safe_method)
{
    for (unsigned int i = 0; i < req_size; ++i) {
        results.push_back(std::make_shared<RenderResult>());

        if (!params[i]->pixels_as_float)
            results[i]->bmp = getColorBufferPool().acquire();
        else
            results[i]->bmp_float = getFloatBufferPool().acquire();
        results[i]->time_stamp = 0;
    }

    CheckNotBlockedOnRenderThread();

    if (use_safe_method) {
        for (unsigned int i = 0; i < req_size; ++i) {
            FIntPoint img_size;
            if (!params[i]->pixels_as_float) {
                FTextureRenderTargetResource* rt_resource = params[i]->render_target->GameThread_GetRenderTargetResource();
                auto flags = setupRenderResource(rt_resource, params[i].get(), results[i].get(), img_size);
                rt_resource->ReadPixels(results[i]->bmp, flags);
            }
            else {
                FTextureRenderTargetResource* rt_resource = params[i]->render_target->GetRenderTargetResource();
                setupRenderResource(rt_resource, params[i].get(), results[i].get(), img_size);
                rt_resource->ReadFloat16Pixels(results[i]->bmp_float);
            }
        }
    }
    else {
        params_ = params;
        results_ = results.data();
        req_size_ = req_size;

        AsyncTask(ENamedThreads::GameThread, [this]() {
            check(IsInGameThread());

            saved_DisableWorldRendering_ = game_viewport_->bDisableWorldRendering;
            game_viewport_->bDisableWorldRendering = 0;
            end_draw_handle_ = game_viewport_->OnEndDraw().AddLambda([this] {
                check(IsInGameThread());

                query_camera_pose_cb_();

                RenderRequest* This = this;
                ENQUEUE_RENDER_COMMAND(SceneDrawCompletion)
                (
                    [This](FRHICommandListImmediate& RHICmdList) {
                        This->ExecuteTask();
                    });

                game_viewport_->bDisableWorldRendering = saved_DisableWorldRendering_;

                assert(end_draw_handle_.IsValid());
                game_viewport_->OnEndDraw().Remove(end_draw_handle_);
            });

            for (unsigned int i = 0; i < req_size_; ++i) {
                params_[i]->render_component->CaptureSceneDeferred();
            }
        });

        while (!wait_signal_->waitFor(5)) {
            UE_LOG(LogTemp, Warning, TEXT("Failed: timeout waiting for screenshot"));
        }
    }

    for (unsigned int i = 0; i < req_size; ++i) {
        if (!params[i]->pixels_as_float) {
            if (results[i]->width != 0 && results[i]->height != 0) {
                const int32 w = results[i]->width;
                const int32 h = results[i]->height;
                const int32 bmp_count = results[i]->bmp.Num();
                const int32 stride = (h > 0) ? (bmp_count / h) : w;

                const bool need_strip = (stride != w);
                TArray<FColor> stripped;
                const TArray<FColor>& src_bmp = [&]() -> const TArray<FColor>& {
                    if (need_strip) {
                        stripped.SetNumUninitialized(w * h);
                        const FColor* src = results[i]->bmp.GetData();
                        FColor* dst = stripped.GetData();
                        for (int32 row = 0; row < h; ++row) {
                            FMemory::Memcpy(dst + row * w, src + row * stride, w * sizeof(FColor));
                        }
                        return stripped;
                    }
                    return results[i]->bmp;
                }();

                if (params[i]->compress_quality > 0) {
                    UAirBlueprintLib::CompressImageArrayJPEG(w, h, src_bmp, results[i]->image_data_uint8, params[i]->compress_quality);
                }
                else if (params[i]->compress_quality == -1 || params[i]->compress) {
                    UAirBlueprintLib::CompressImageArray(w, h, src_bmp, results[i]->image_data_uint8);
                }
                else {
                    results[i]->image_data_uint8.SetNumUninitialized(w * h * 3, false);
                    uint8* ptr = results[i]->image_data_uint8.GetData();
                    const FColor* raw_src = results[i]->bmp.GetData();
                    for (int32 row = 0; row < h; ++row) {
                        const FColor* src_row = raw_src + row * stride;
                        for (int32 col = 0; col < w; ++col) {
                            *ptr++ = src_row[col].B;
                            *ptr++ = src_row[col].G;
                            *ptr++ = src_row[col].R;
                        }
                    }
                }
            }
            getColorBufferPool().release(MoveTemp(results[i]->bmp));
        }
        else {
            const int32 w = results[i]->width;
            const int32 h = results[i]->height;
            const int32 bmp_count = results[i]->bmp_float.Num();
            const int32 stride = (h > 0) ? (bmp_count / h) : w;

            results[i]->image_data_float.SetNumUninitialized(w * h);
            float* ptr = results[i]->image_data_float.GetData();
            const FFloat16Color* src = results[i]->bmp_float.GetData();
            for (int32 row = 0; row < h; ++row) {
                const FFloat16Color* src_row = src + row * stride;
                for (int32 col = 0; col < w; ++col) {
                    *ptr++ = src_row[col].R.GetFloat();
                }
            }
            getFloatBufferPool().release(MoveTemp(results[i]->bmp_float));
        }
    }
}

FReadSurfaceDataFlags RenderRequest::setupRenderResource(const FTextureRenderTargetResource* rt_resource, const RenderParams* params, RenderResult* result, FIntPoint& size)
{
    size = rt_resource->GetSizeXY();
    result->width = size.X;
    result->height = size.Y;
    FReadSurfaceDataFlags flags(RCM_UNorm, CubeFace_MAX);
    flags.SetLinearToGamma(false);

    return flags;
}

void RenderRequest::ExecuteTask()
{
    if (params_ != nullptr && req_size_ > 0) {
        for (unsigned int i = 0; i < req_size_; ++i) {
            FRHICommandListImmediate& RHICmdList = GetImmediateCommandList_ForRenderCommand();
            auto rt_resource = params_[i]->render_target->GetRenderTargetResource();
            if (rt_resource != nullptr) {
                const FTextureRHIRef& rhi_texture = rt_resource->GetRenderTargetTexture();
                FIntPoint size;
                auto flags = setupRenderResource(rt_resource, params_[i].get(), results_[i].get(), size);

                if (!params_[i]->pixels_as_float) {
                    results_[i]->bmp.Reserve(size.X * size.Y);
                    RHICmdList.ReadSurfaceData(
                        rhi_texture,
                        FIntRect(0, 0, size.X, size.Y),
                        results_[i]->bmp,
                        flags);
                }
                else {
                    results_[i]->bmp_float.Reserve(size.X * size.Y);
                    RHICmdList.ReadSurfaceFloatData(
                        rhi_texture,
                        FIntRect(0, 0, size.X, size.Y),
                        results_[i]->bmp_float,
                        CubeFace_PosX,
                        0,
                        0);
                }
            }

            results_[i]->time_stamp = msr::airlib::ClockFactory::get()->nowNanos();
        }

        req_size_ = 0;
        params_ = nullptr;
        results_ = nullptr;

        wait_signal_->signal();
    }
}
