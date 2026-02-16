# NumPy

## Rol en el proyecto
- Representar frames como arrays.
- Operaciones vectorizadas para filtros.

## Arquitectura basica
- ndarray: estructura principal.
- dtype: tipo de dato (uint8 para imagenes).
- shape: (alto, ancho, canales).

## Buenas practicas
- Evitar loops Python por pixel.
- Usar dtype uint8 para compatibilidad con cv2.
- Mantener copias al minimo.
