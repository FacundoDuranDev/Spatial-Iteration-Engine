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

    # ── Mesh ───────────────────────────────────────────────────────

    def test_default_mesh_size_is_2x2(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        self.assertEqual(r.mesh_size, (2, 2))
        self.assertTrue(r.is_identity())

    def test_set_mesh_size_supported_density_resets_to_identity(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        r.set_mesh_size(5, 5)
        self.assertEqual(r.mesh_size, (5, 5))
        self.assertTrue(r.is_identity())
        # Cambio de densidad ⇒ se pierde calibración previa (esto es a propósito).
        r.set_mesh_point(2, 2, 0.4, 0.4)
        self.assertFalse(r.is_identity())
        r.set_mesh_size(3, 3)
        self.assertTrue(r.is_identity())

    def test_set_mesh_size_invalid_density_raises(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        with self.assertRaises(ValueError):
            r.set_mesh_size(7, 7)  # No está en SUPPORTED_MESH_SIZES.

    def test_set_mesh_point_clamps_and_invalidates_lut(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        r.set_mesh_size(3, 3)
        r.set_mesh_point(1, 1, -0.2, 1.5)
        pts = r.mesh_points
        self.assertEqual(pts[1][1], [0.0, 1.0])
        # LUT se invalida en cada cambio — el slot de la active region.
        self.assertIsNone(r._lut_caches[r.active_region_index])

    def test_mesh_warp_renders_through_remap_path(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers import (
            PassthroughRenderer,
            ProjectionMappingRenderer,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        renderer = ProjectionMappingRenderer(
            inner=PassthroughRenderer(), mesh_size=(3, 3), enabled=True,
        )
        # Encoger todo el mesh 20% hacia el centro — 9 puntos movidos.
        for i in range(3):
            for j in range(3):
                base_x = j * 0.5
                base_y = i * 0.5
                cx = 0.5 + (base_x - 0.5) * 0.6
                cy = 0.5 + (base_y - 0.5) * 0.6
                renderer.set_mesh_point(i, j, cx, cy)
        frame = np.full((40, 60, 3), 200, dtype=np.uint8)
        config = EngineConfig(raw_width=60, raw_height=40)
        out = renderer.render(frame, config)
        arr = np.asarray(out.image)
        # Bordes del frame quedan en negro (fuera de los triángulos rasterizados).
        self.assertLess(arr[0:3, :, :].mean(), 30.0)
        self.assertLess(arr[-3:, :, :].mean(), 30.0)
        # Centro del frame conserva intensidad alta (el contenido se metió ahí).
        self.assertGreater(arr[18:22, 28:32, :].mean(), 150.0)
        self.assertEqual(out.metadata.get("projection"), "warped")
        self.assertEqual(out.metadata.get("projection_regions_total"), 1)
        self.assertEqual(out.metadata.get("projection_regions_active"), 1)
        # LUT cacheado tras el primer render.
        self.assertIsNotNone(renderer._lut_caches[0])

    def test_mesh_lut_cache_invalidates_when_mesh_changes(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers import (
            PassthroughRenderer,
            ProjectionMappingRenderer,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        renderer = ProjectionMappingRenderer(
            inner=PassthroughRenderer(), mesh_size=(3, 3), enabled=True,
        )
        renderer.set_mesh_point(1, 1, 0.4, 0.4)
        frame = np.full((30, 40, 3), 128, dtype=np.uint8)
        config = EngineConfig(raw_width=40, raw_height=30)
        renderer.render(frame, config)
        first_sig = renderer._lut_caches[0][4]
        renderer.set_mesh_point(1, 1, 0.6, 0.6)
        renderer.render(frame, config)
        self.assertNotEqual(renderer._lut_caches[0][4], first_sig)

    def test_legacy_corner_api_still_works_on_2x2(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer(
            corners=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.1, 0.95)],
            enabled=True,
        )
        self.assertEqual(r.mesh_size, (2, 2))
        c = r.corners_norm
        self.assertAlmostEqual(c[3][0], 0.1)
        r.set_corner(2, 0.95, 0.95)
        self.assertAlmostEqual(r.corners_norm[2][0], 0.95)

    # ── Multi-region ──────────────────────────────────────────────

    def test_default_renderer_has_one_region(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        self.assertEqual(len(r.regions), 1)
        self.assertEqual(r.active_region_index, 0)
        self.assertEqual(r.active_region.name, "Región 1")

    def test_add_region_increments_active(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        idx = r.add_region("Pared izquierda")
        self.assertEqual(idx, 1)
        self.assertEqual(len(r.regions), 2)
        self.assertEqual(r.active_region_index, 1)
        self.assertEqual(r.active_region.name, "Pared izquierda")

    def test_remove_region_keeps_at_least_one(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        r.add_region()
        r.add_region()
        self.assertEqual(len(r.regions), 3)
        r.remove_region(1)
        self.assertEqual(len(r.regions), 2)
        with self.assertRaises(ValueError):
            r.remove_region(0)
            r.remove_region(0)  # Aquí debería tirar — ya queda solo 1.

    def test_legacy_proxies_target_active_region(self) -> None:
        from ascii_stream_engine.adapters.renderers import ProjectionMappingRenderer

        r = ProjectionMappingRenderer()
        r.add_region()
        r.set_active_region(1)
        r.set_mesh_point(0, 0, 0.2, 0.2)
        # Solo la active (la 1) debe estar fuera de identidad.
        self.assertFalse(r.regions[1].is_identity())
        self.assertTrue(r.regions[0].is_identity())

    def test_composite_render_with_two_regions(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers import (
            PassthroughRenderer,
            ProjectionMappingRenderer,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        renderer = ProjectionMappingRenderer(
            inner=PassthroughRenderer(), enabled=True,
        )
        # Región 0 (active): cuadrante superior izquierdo
        renderer.set_corners([
            (0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5),
        ])
        # Región 1: cuadrante inferior derecho
        renderer.add_region("Bottom right")
        renderer.set_corners([
            (0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0),
        ])
        frame = np.full((40, 60, 3), 220, dtype=np.uint8)
        out = renderer.render(frame, EngineConfig(raw_width=60, raw_height=40))
        arr = np.asarray(out.image)
        # Cuadrantes opuestos vacíos (negro): el TR y el BL.
        self.assertLess(arr[0:18, 32:60, :].mean(), 30.0)
        self.assertLess(arr[22:40, 0:28, :].mean(), 30.0)
        # Cuadrantes con regiones tienen contenido (no son negros).
        self.assertGreater(arr[0:18, 0:28, :].mean(), 100.0)
        self.assertGreater(arr[22:40, 32:60, :].mean(), 100.0)
        self.assertEqual(out.metadata.get("projection_regions_active"), 2)

    def test_disabled_region_not_rendered(self) -> None:
        import numpy as np

        from ascii_stream_engine.adapters.renderers import (
            PassthroughRenderer,
            ProjectionMappingRenderer,
        )
        from ascii_stream_engine.domain.config import EngineConfig

        renderer = ProjectionMappingRenderer(
            inner=PassthroughRenderer(), enabled=True,
        )
        renderer.set_corners([(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)])
        renderer.add_region()
        renderer.set_corners([(0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)])
        renderer.set_region_enabled(1, False)
        frame = np.full((40, 60, 3), 220, dtype=np.uint8)
        out = renderer.render(frame, EngineConfig(raw_width=60, raw_height=40))
        # Solo region 0 (TL) renderiza; el cuadrante BR queda vacío.
        arr = np.asarray(out.image)
        self.assertGreater(arr[0:18, 0:28, :].mean(), 100.0)
        self.assertLess(arr[22:40, 32:60, :].mean(), 30.0)
        self.assertEqual(out.metadata.get("projection_regions_active"), 1)


if __name__ == "__main__":
    unittest.main()
