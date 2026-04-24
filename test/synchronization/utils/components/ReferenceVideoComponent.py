from . import VideoComponent

class ReferenceVideoComponent(VideoComponent):
    def update_camera(self, ref_timestamp):
        # Reference cameras override camera callback to match frame
        #   by closest `frame_timestamp` among each other, selected by frame slider.
        self._current_frame_id = self.get_frame_for_timestamp(ref_timestamp)
        return self._generate_patch_from_frame(self._current_frame_id)
