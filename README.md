# GanadoBravo Fullstack IA (GPT-4o) con Categorías

## 🚀 Cómo correr localmente
1. Crear entorno virtual e instalar dependencias:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Definir variable de entorno con tu API key de OpenAI:
   ```bash
   export OPENAI_API_KEY="sk-xxxxx"
   ```

3. Correr el servidor:
   ```bash
   uvicorn main:app --reload
   ```

4. Abrir en navegador:
   [http://localhost:8000/](http://localhost:8000/)

## 🚀 Deploy en Railway
1. Sube este repo a GitHub.
2. Conecta el repo en Railway.
3. Configura la variable de entorno `OPENAI_API_KEY` en Railway.
4. Railway usará `Procfile` para iniciar el servidor.
