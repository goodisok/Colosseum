// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

#ifndef air_EncodedImageCaptureBase_hpp
#define air_EncodedImageCaptureBase_hpp

#include "common/Common.hpp"
#include "common/ImageCaptureBase.hpp"

namespace msr
{
namespace airlib
{

    class EncodedImageCaptureBase
    {
    public:
        enum class EncodeMode : int
        {
            NvencH264 = 1,
            NvencHevc = 2,
            Png16 = 3,
            Exr = 4
        };

        enum class EncodedPixFmt : int
        {
            Yuv420 = 0,
            Yuv444 = 1,
            Gbrp = 2
        };

        struct EncodedImageRequest
        {
            std::string camera_name;
            ImageCaptureBase::ImageType image_type = ImageCaptureBase::ImageType::Scene;
            EncodeMode encode_mode = EncodeMode::NvencH264;
            bool lossless = false;
            int cq_or_qp = 23;
            int gop_size = 1;
            EncodedPixFmt pix_fmt = EncodedPixFmt::Yuv420;

            EncodedImageRequest()
            {
            }

            EncodedImageRequest(const std::string& camera_name_val,
                                ImageCaptureBase::ImageType image_type_val,
                                EncodeMode encode_mode_val,
                                bool lossless_val = false,
                                int cq_or_qp_val = 23,
                                int gop_size_val = 1,
                                EncodedPixFmt pix_fmt_val = EncodedPixFmt::Yuv420)
                : camera_name(camera_name_val)
                , image_type(image_type_val)
                , encode_mode(encode_mode_val)
                , lossless(lossless_val)
                , cq_or_qp(cq_or_qp_val)
                , gop_size(gop_size_val)
                , pix_fmt(pix_fmt_val)
            {
            }
        };

        struct EncodedImageResponse
        {
            vector<uint8_t> bitstream;

            std::string camera_name;
            Vector3r camera_position = Vector3r::Zero();
            Quaternionr camera_orientation = Quaternionr::Identity();
            TTimePoint time_stamp = 0;
            std::string message;

            int width = 0, height = 0;
            ImageCaptureBase::ImageType image_type = ImageCaptureBase::ImageType::Scene;
            EncodeMode encode_mode = EncodeMode::NvencH264;
            EncodedPixFmt pix_fmt = EncodedPixFmt::Yuv420;
            int encoded_size = 0;
        };
    };
}
} //namespace
#endif
