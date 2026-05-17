#!/bin/bash
sudo cp -rv /opt/tros/humble/share/hobot_stereonet/script/run_stereo.sh ./
sudo bash run_stereo.sh --mipi_rotation 0.0 --stereonet_frame_id camera_Link