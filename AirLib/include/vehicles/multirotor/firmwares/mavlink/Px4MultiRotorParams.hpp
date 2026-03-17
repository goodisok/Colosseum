// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

#ifndef msr_airlib_vehicles_Px4MultiRotor_hpp
#define msr_airlib_vehicles_Px4MultiRotor_hpp

#include "vehicles/multirotor/firmwares/mavlink/MavLinkMultirotorApi.hpp"
#include "common/AirSimSettings.hpp"
#include "sensors/SensorFactory.hpp"
#include "vehicles/multirotor/MultiRotorParams.hpp"

namespace msr
{
namespace airlib
{

    class Px4MultiRotorParams : public MultiRotorParams
    {
    public:
        Px4MultiRotorParams(const AirSimSettings::MavLinkVehicleSetting& vehicle_setting, std::shared_ptr<const SensorFactory> sensor_factory)
            : sensor_factory_(sensor_factory)
        {
            connection_info_ = getConnectionInfo(vehicle_setting);
        }

        virtual ~Px4MultiRotorParams() = default;

        virtual std::unique_ptr<MultirotorApiBase> createMultirotorApi() override
        {
            unique_ptr<MultirotorApiBase> api(new MavLinkMultirotorApi());
            auto api_ptr = static_cast<MavLinkMultirotorApi*>(api.get());
            api_ptr->initialize(connection_info_, &getSensors(), true);

            return api;
        }

        virtual void setupParams() override
        {
            auto& params = getParams();

            if (connection_info_.model == "Blacksheep") {
                setupFrameBlacksheep(params);
            }
            else if (connection_info_.model == "Flamewheel") {
                setupFrameFlamewheel(params);
            }
            else if (connection_info_.model == "FlamewheelFLA") {
                setupFrameFlamewheelFLA(params);
            }
            else if (connection_info_.model == "Hexacopter") {
                setupFrameGenericHex(params);
            }
            else if (connection_info_.model == "Octocopter") {
                setupFrameGenericOcto(params);
            }
            else if (connection_info_.model == "HighSpeedIntercept") {
                setupFrameHighSpeedQuad(params);
            }
            else //Generic
                setupFrameGenericQuad(params);
        }

    protected:
        virtual const SensorFactory* getSensorFactory() const override
        {
            return sensor_factory_.get();
        }

    private:

        // void setupFrameHighSpeedQuad(Params& params)
        // {
        //     params.rotor_count = 4;
        //     std::vector<real_T> arm_lengths(params.rotor_count, 0.30f);
        //     params.mass = 2.5f;
        //     real_T motor_assembly_weight = 0.10f;
        //     real_T box_mass = params.mass - params.rotor_count * motor_assembly_weight;
            
        //     params.rotor_params.C_T = 0.15f;           // +36%
        //     params.rotor_params.C_P = 0.055f;          // +37%
        //     params.rotor_params.max_rpm = 10000;       // +56%
        //     params.rotor_params.propeller_diameter = 0.3048f; // +33%
        //     params.rotor_params.propeller_height = 0.03f;
        //     params.rotor_params.calculateMaxThrust();
            
        //     params.linear_drag_coefficient = 0.20f;  
        //     params.angular_drag_coefficient = 0.04f;
            
        //     params.body_box.x() = 0.25f;
        //     params.body_box.y() = 0.20f;
        //     params.body_box.z() = 0.15f;
        //     real_T rotor_z = 0.05f;
            
        //     initializeRotorQuadX(params.rotor_poses, params.rotor_count, 
        //                     arm_lengths.data(), rotor_z);
        //     computeInertiaMatrix(params.inertia, params.body_box, params.rotor_poses, 
        //                     box_mass, motor_assembly_weight);
        // }

        void setupFrameHighSpeedQuad(Params& params)
        {
            //set up arm lengths
            //dimensions are for F450 frame: http://artofcircuits.com/product/quadcopter-frame-hj450-with-power-distribution
            params.rotor_count = 4;
            std::vector<real_T> arm_lengths(params.rotor_count, 0.2275f);

            //set up mass
            //this has to be between max_thrust*rotor_count/10 (1.6kg using default parameters in RotorParams.hpp) and (idle throttle percentage)*max_thrust*rotor_count/10 (0.8kg using default parameters and SimpleFlight)
            //any value above the maximum would result in the motors not being able to lift the body even at max thrust,
            //and any value below the minimum would cause the drone to fly upwards on idling throttle (50% of the max throttle if using SimpleFlight)
            //Note that the default idle throttle percentage is 50% if you are using SimpleFlight
            params.mass = 1.0f;

            real_T motor_assembly_weight = 0.055f; //weight for MT2212 motor for F450 frame
            real_T box_mass = params.mass - params.rotor_count * motor_assembly_weight;


            params.linear_drag_coefficient = 1.3f / 20.0f;

            // using rotor_param default, but if you want to change any of the rotor_params, call calculateMaxThrust() to recompute the max_thrust
            // given new thrust coefficients, motor max_rpm and propeller diameter.
            params.rotor_params.calculateMaxThrust();

            //set up dimensions of core body box or abdomen (not including arms).
            params.body_box.x() = 0.180f;
            params.body_box.y() = 0.11f;
            params.body_box.z() = 0.040f;
            real_T rotor_z = 2.5f / 100;

            //computer rotor poses
            initializeRotorQuadX(params.rotor_poses, params.rotor_count, arm_lengths.data(), rotor_z);

            //compute inertia matrix
            computeInertiaMatrix(params.inertia, params.body_box, params.rotor_poses, box_mass, motor_assembly_weight);
        }


        static const AirSimSettings::MavLinkConnectionInfo& getConnectionInfo(const AirSimSettings::MavLinkVehicleSetting& vehicle_setting)
        {
            return vehicle_setting.connection_info;
        }

    private:
        AirSimSettings::MavLinkConnectionInfo connection_info_;
        std::shared_ptr<const SensorFactory> sensor_factory_;
    };
}
} //namespace
#endif
