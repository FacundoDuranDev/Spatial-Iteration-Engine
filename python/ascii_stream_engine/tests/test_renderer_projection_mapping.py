import unittest

from ascii_stream_engine.tests import has_module


@unittest.skipUnless(
    has_module("cv2") and has_module("numpy") and has_module("PIL"),
    "requires cv2, numpy, pillow",
)
class TestProjectionMappingRenderer(unittest.TestCase):
    def _make_frame(self):
        import numpy as np

        # 80×60 RGB con un cuadrado blanco arriba a la izquierda — fácil de
        # asertar dónde queda después del warp.
        frame = np.zeros((60, 80, 3), dtype=np.uint8)
        frame[0:20, 0:20] = 255
        return frame

    def _config(self):
        from ascii_stream_engine.domain.config import EngineConfig

        return EngineConfig(raw_width=80, raw_height=60)

    def test_passthrough_when_disabled(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers import (
            PassthroughRenderer,
            ProjectionMappingRenderer,
        )

        inner = PassthroughRenderer()
        renderer = ProjectionMappingRenderer(inner=inner, enabled=False)
        out = renderer.render(self._make_frame(), self._config())
        self.assertEqual(out.image.size, (80, 60))
        # Identidad + disabled → nunca debería aparecer la marca de warp.
        self.assertNotIn("projection", out.metadata or {})

    def test_passthrough_when_corners_are_identity(self) -> None:
        from ascii_stream_engine.adapters.renderers import (
            PassthroughRenderer,
            ProjectionMappingRenderer,
        )

        renderer = ProjectionMappingRenderer(
            inner=PassthroughRenderer(),
            enabled=True,
        )
        self.assertTrue(renderer.is_identity())
        out = renderer.render(self._make_frame(), self._config())
        # Enabled pero con corners identity → corto-circuito sin metadata.
        self.assertNotIn("projection", out.metadata or {})

    def test_warp_applied_when_corners_shifted(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers import (
            PassthroughRenderer,
            ProjectionMappingRenderer,
        )

        # Squash horizontal: la mitad derecha colapsa contra el centro.
        renderer = ProjectionMappingRenderer(
            inner=PassthroughRenderer(),
            corners=[(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)],
            enabled=True,
        )
        self.assertFalse(renderer.is_identity())
        out = renderer.render(self._make_frame(), self._config())
        arr = np.asarray(out.image)
        # El cuadrado blanco original (0:20, 0:20) tiene que terminar más
        # apretado en la mitad izquierda; la mitad derecha de la salida
        # quedó con el border value (negro).
        right_half_mean = arr[:, 40:, :].mean()
        self.assertLess(right_half_mean, 5.0)
        self.assertEqual(out.metadata.get("projection"), "warped")

    def test_set_corner_clamps_to_unit_square(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        r.set_corner(0, -0.5, 1.4)
        c = r.corners_norm[0]
        self.assertEqual(c, (0.0, 1.0))

    def test_reset_returns_to_identity(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer(
            corners=[(0.1, 0.0), (0.9, 0.1), (0.95, 0.9), (0.05, 1.0)],
            enabled=True,
        )
        self.assertFalse(r.is_identity())
        r.reset()
        self.assertTrue(r.is_identity())

    def test_invalid_corner_count_raises(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        with self.assertRaises(ValueError):
            ProjectionMappingRenderer(corners=[(0, 0), (1, 0), (1, 1)])

    def test_overlay_capable_alias_toggles_enabled(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        self.assertFalse(r.overlay_enabled)
        r.overlay_enabled = True
        self.assertTrue(r.enabled)
        r.overlay_enabled = False
        self.assertFalse(r.enabled)


if __name__ == "__main__":
    unittest.main()
