# Cómo quitar el cuadro de “Calidad de entrada” en tu frontend

Hay dos formas incluidas:

1) **Frontline limpio (este index.html)**  
   - No renderiza el cuadro en absoluto. Úsalo tal cual (carpeta `static/`).

2) **Eliminación forzada**  
   - En caso de que un bundle viejo inyecte ese bloque, un script JS lo **borra del DOM** buscando textos:  
     “Calidad de entrada”, “Estabilidad”, “Rúbrica:”, “Porción visible”.  
   - Esto funciona aunque el layout cambie o sea React/SSR.

Si tu proyecto es React/Vite:
- Busca el componente que renderiza ese bloque (ej: `QualityRow`, `QualityBar`, `QCChips`)
  y **elimínalo o retorna null**:
```tsx
export function QualityRow(){ return null; } // quitar definitivamente
```
- Alternativamente, añade a `index.html` de `public/` el script de eliminación forzada.
