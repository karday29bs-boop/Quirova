# Quirova – Quirófano Predictivo

Plataforma web sencilla para organizar la preparación de procedimientos quirúrgicos y estimar su riesgo de retraso con un modelo predictivo local.

> Herramienta de apoyo operativo con fines de prueba. No sustituye el criterio clínico ni los protocolos institucionales.

## Requisitos

- Python 3.9 o superior.
- No hay que instalar librerías: todo usa la biblioteca estándar de Python.

## Cómo ejecutarlo

```bash
python3 app.py
```

Abre http://localhost:8000 e inicia sesión con el usuario de prueba:

| Correo | Contraseña |
|---|---|
| `pruebaQuirofano@correo.com` | `quirofano123` |

El usuario está definido directamente en `server.py`. Sirve solo para desarrollo y pruebas.

## Secciones

| Sección | Para qué sirve |
|---|---|
| Inicio | Bienvenida y accesos rápidos. |
| Guía de uso | Recorrido de 6 pasos por la plataforma. |
| Configuración | Institución, quirófanos, equipos y permisos. |
| Procedimientos | Programar procedimientos y ver la predicción de retrasos de todos. |
| Preparación | Índice de Preparación Quirúrgica (IPQ) y memoria del cirujano. |
| Simulación | Preparación paso a paso y predicción detallada de un procedimiento. |
| Trazabilidad | Registros de seguimiento por módulo: instrumental, esterilización, dispositivos y mantenimiento. |
| Reportes | Resumen de toda la información registrada. |

### Índice de Preparación Quirúrgica (IPQ)

Cada procedimiento se evalúa en 7 componentes: instrumental, insumos, dispositivos médicos, mantenimiento biomédico, esterilización, documentación y equipo quirúrgico. Cada componente se marca como *Listo*, *Pendiente* o *No aplica*.

**IPQ = componentes listos ÷ componentes que aplican**

| IPQ | Nivel |
|---|---|
| 90 % o más | Preparación alta |
| De 70 % a 89 % | Preparación media |
| Menos de 70 % | Preparación baja |

## Estructura del proyecto

```
app.py             Arranca el servidor local
server.py          Lógica del servidor: login, páginas y API (local y Vercel)
model.py           Modelo predictivo local
seed_data.json     Datos de prueba iniciales
templates/
  index.html       La plataforma
  login.html       Pantalla de inicio de sesión
api/index.py       Función de Vercel (usa server.py)
vercel.json        Configuración de Vercel
```

## Cómo se guardan los datos

- Todo lo que registras se guarda **en el navegador** (localStorage) con cada cambio, así que se mantiene al recargar y al cerrar el navegador.
- Cada navegador tiene sus propios datos: no se comparten entre personas ni entre computadores.
- La primera vez que entras, la plataforma carga los datos de prueba de `seed_data.json`.
- **Para volver a los datos de prueba**, borra los datos del sitio en el navegador. En Chrome: candado de la barra de direcciones → *Configuración del sitio* → *Borrar datos*.
- La sesión es una cookie firmada que dura 30 días o hasta que pulses *Cerrar sesión*. El servidor no guarda nada en disco.

## El modelo predictivo

`model.py` contiene un modelo que predice, para cada procedimiento:

- **Riesgo de retraso** (0–100 %): bajo si es menor de 30 %, medio hasta 59 % y alto desde 60 %.
- **Duración estimada**: parte de una duración de referencia según el tipo de cirugía y aumenta cuanto mayor es el riesgo.
- **Factores principales**: las 3 variables que más influyen en el resultado, y si aumentan o reducen el riesgo.

### Cómo funciona

Es una **regresión logística** escrita en Python puro. Usa 5 variables que salen de lo registrado en la plataforma:

| Variable | Efecto esperado |
|---|---|
| IPQ del procedimiento | Más preparación → menos riesgo |
| Componentes pendientes | Más pendientes → más riesgo |
| Componentes sin evaluar | Más sin evaluar → más riesgo |
| Registros de trazabilidad | Más seguimiento → menos riesgo |
| Días hasta la cirugía | Más tiempo para preparar → menos riesgo |

- El modelo se **entrena al arrancar el servidor**, en menos de un segundo, con 800 casos simulados. Usa una semilla fija, así que siempre da el mismo resultado.
- Las predicciones se calculan **solo al pulsar** *Calcular predicción* en Procedimientos o en Simulación.
- Si cambias datos después de calcular, la página avisa que hay cambios sin recalcular.

Para ver el resultado del entrenamiento y los pesos del modelo:

```bash
python3 model.py
```

### Limitaciones

El modelo aprende de **datos simulados**, así que sus cifras sirven para probar la plataforma, no para tomar decisiones reales. Para usar un historial real, reemplaza la función `synthetic_history()` de `model.py` por una que cargue casos reales. Cada caso necesita los valores de las 5 variables y si hubo retraso (0 o 1).

## API

Todas las rutas requieren haber iniciado sesión.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/seed` | Devuelve los datos de prueba iniciales. |
| `POST` | `/api/predicciones` | Recibe los datos del navegador (JSON) y devuelve las predicciones. No guarda nada. |

## Despliegue en Vercel

El proyecto está listo para Vercel: todas las rutas pasan por la función `api/index.py`.

1. Sube el proyecto a GitHub.
2. En [vercel.com](https://vercel.com), elige *Add New → Project* e importa el repositorio. Deja *Framework Preset* en **Other**.
3. Antes de desplegar, en *Environment Variables* agrega `QUIROVA_SECRET` con un valor largo y aleatorio. Puedes generarlo con:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Sin esta variable se usa una clave de desarrollo que está en el código, y cualquiera podría falsificar una sesión.
4. Pulsa *Deploy*. Cada `git push` a `main` vuelve a desplegar automáticamente.

También puedes desplegar desde la terminal con la [CLI de Vercel](https://vercel.com/docs/cli): `npx vercel` y luego `npx vercel --prod`.
