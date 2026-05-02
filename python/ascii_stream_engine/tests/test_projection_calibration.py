import unittest

from ascii_stream_engine.tests import has_module


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2, numpy",
)
class TestProjectionCalibration(unittest.TestCase):
    def test_generate_pattern_returns_rgb_uint8_at_requested_size(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers.projection_calibration import (
            generate_pattern_image,
        )

        img = generate_pattern_image(640, 360)
        self.assertEqual(img.shape, (360, 640, 3))
        self.assertEqual(img.dtype, np.uint8)
        # No es un canvas plano — el patrón tiene contraste.
        self.assertGreater(img.std(), 50.0)

    def test_pattern_is_cached_per_size(self) -> None:
        from ascii_stream_engine.adapters.renderers.projection_calibration import (
            generate_pattern_image,
            _PATTERN_CACHE,
        )

        a = generate_pattern_image(320, 200)
        b = generate_pattern_image(320, 200)
        # Mismo array — el cache debe devolver la misma referencia.
        self.assertIs(a, b)
        self.assertIn((320, 200), _PATTERN_CACHE)

    def test_detect_corners_on_unwarped_pattern_returns_full_quad(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers.projection_calibration import (
            generate_pattern_image,
            detect_corners_normalized,
        )

        # "Captura" sintética: el patrón mismo, sin warp ni cámara real.
        # El detector tiene que decir "esto cubre todo el frame [0,1]".
        pattern = generate_pattern_image(800, 600)
        corners, err = detect_corners_normalized(pattern)
        self.assertIsNone(err, msg=err)
        self.assertEqual(len(corners), 4)
        # Como no hay warp, los 4 corners deberían estar cerca de los corners
        # del unit square (con tolerancia por el margen blanco del pattern).
        # TL y BR son los más informativos.
        self.assertLess(corners[0][0], 0.2); self.assertLess(corners[0][1], 0.2)
        self.assertGreater(corners[2][0], 0.8); self.assertGreater(corners[2][1], 0.8)

    def test_detect_corners_returns_error_on_blank_frame(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers.projection_calibration import (
            detect_corners_normalized,
        )

        blank = np.zeros((200, 300, 3), dtype=np.uint8)
        corners, err = detect_corners_normalized(blank)
        self.assertIsNone(corners)
        self.assertIsInstance(err, str)
        self.assertIn("markers", err)


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy"),
    "requires cv2, numpy",
)
class TestRendererCalibrationMode(unittest.TestCase):
    def test_renderer_emits_pattern_in_calibration_mode(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers import (
            PassthroughRenderer,
            ProjectionMappingRenderer,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        renderer = ProjectionMappingRenderer(inner=PassthroughRenderer())
        renderer.calibration_mode = True
        frame = np.zeros((100, 160, 3), dtype=np.uint8)
        out = renderer.render(frame, EngineConfig(raw_width=160, raw_height=100))
        self.assertEqual(out.metadata.get("calibration"), True)
        # El output ignoró el frame de entrada y generó el patrón.
        arr = np.asarray(out.image)
        self.assertGreater(arr.std(), 50.0)


if __name__ == "__main__":
    unittest.main()
