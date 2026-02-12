# Aluekehityksen dashboard (Streamlit)

# Run and deploy your AI Studio app
Tämä projekti on Python-pohjainen Streamlit-dashboard, joka hakee Kaustisen seudun kuntakohtaiset avainluvut Tilastokeskuksen StatFin-rajapinnasta ja visualisoi ne interaktiivisesti.

This contains everything you need to run your app locally.
## Sisältö

View your app in AI Studio: https://ai.studio/apps/drive/17CEAMEMCcnWw_4nJkVVNoJlzZKfzrJZH
- `streamlit_app.py` – varsinainen Streamlit-sovellus
- `statfin_service.py` – datan haku ja muunnos StatFin API:sta
- `.streamlit/config.toml` – Streamlitin ajokonfiguraatio
- `requirements.txt` – riippuvuudet Streamlit Cloudille
- `runtime.txt` – Python-versio deploy-ympäristöön

## Run Locally
## Paikallinen ajo

**Prerequisites:**  Node.js
1. Luo virtuaaliympäristö:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Asenna riippuvuudet:
   ```bash
   pip install -r requirements.txt
   ```
3. Käynnistä sovellus:
   ```bash
   streamlit run streamlit_app.py
   ```

## Julkaisu Streamlit Cloudiin

1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`
1. Pushaa repository GitHubiin.
2. Avaa [share.streamlit.io](https://share.streamlit.io/) ja valitse **New app**.
3. Valitse repository ja branch.
4. Aseta **Main file path** arvoksi:
   ```
   streamlit_app.py
   ```
5. Deployaa sovellus.

