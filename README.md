# GanadoBravo Fullstack v2 (IA real con GPT-4o)

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
   [http://localhost:8000/static/index.html](http://localhost:8000/static/index.html)

## 📦 Deploy en Render/Heroku
- Usa este repo como fuente, asegúrate de setear `OPENAI_API_KEY` en variables de entorno.
