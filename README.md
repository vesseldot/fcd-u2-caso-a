# Actividad Integradora U2 — Caso A: Monolito vs. Microservicios

[![Abrir en Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/vesseldot/fcd-u2-caso-a/blob/main/notebooks/caso_a_monolito_vs_microservicios.ipynb)

📄 [Reporte técnico (PDF)](docs/Reporte_Tecnico_Caso_A.pdf) · 📓 [Cuaderno](notebooks/caso_a_monolito_vs_microservicios.ipynb)

**Fundamentos de Ciencia de Datos** · Ingeniería en Sistemas Computacionales · TecNM – Instituto Tecnológico de Zacatepec
Docente: Celia Ramos Palencia · Grupo XB

**Equipo:** Muñoz García Jorge (23091000) · Suárez Degante Luis Ángel (23091050) · Hermosa Praxedis Carlos Rafael (23090958) · Morantes Pereida Denzel Yahir (23090999)

## Pregunta
¿La sobrecarga de red de una arquitectura de microservicios incrementa la latencia de respuesta HTTP respecto a un monolito con la misma lógica de negocio?

## Resultado principal
| | Monolito | Microservicios |
|---|---|---|
| Latencia media (ms) | 1.328 | 3.937 |
| Desviación estándar (ms) | 0.184 | 0.492 |
| n (depurado) | 289 | 290 |

- Levene: p = 1.89 × 10⁻³³ → varianzas distintas → **Welch**.
- IC 95 % para μ_micro − μ_mono: **[2.549, 2.670] ms** (0 ∉ IC).
- t de Welch unilateral: t = 84.52, ν = 368.1, **p = 1.75 × 10⁻²⁴³ → se rechaza H₀**.
- Los microservicios añaden ≈ 2.6 ms por petición (≈ 0.87 ms por salto HTTP).

## Datos
Telemetría **real** obtenida con una prueba de carga local (fuente permitida #2): `src/prueba_carga.py` implementa ambas arquitecturas (cada microservicio en su propio proceso) y envía 300 peticiones por arquitectura en orden aleatorio intercalado. Solo usa la biblioteca estándar de Python.

## Estructura
```
data/        dataset_caso_a_raw.csv (600 reg.) y dataset_caso_a_limpio.csv (579 reg.)
notebooks/   caso_a_monolito_vs_microservicios.ipynb  (ejecutado, documentado celda a celda)
docs/        Reporte_Tecnico_Caso_A.pdf y figuras/
src/         prueba_carga.py  (arquitecturas + prueba de carga)
```

## Reproducción
```bash
pip install -r requirements.txt
python src/prueba_carga.py 300        # opcional: regenera la telemetría (los valores absolutos dependen del equipo)
jupyter nbconvert --to notebook --execute --inplace notebooks/caso_a_monolito_vs_microservicios.ipynb
```
El cuaderno funciona desde la raíz del repo, desde `notebooks/` o en Google Colab (con el botón de arriba; si no encuentra `data/`, descarga el CSV desde este repositorio).
