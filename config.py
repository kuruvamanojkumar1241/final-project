import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'lung-cancer-ai-secret-key'
    DATABASE = os.path.join('database', 'lung_ai.db')
    UPLOAD_FOLDER = os.path.join('static', 'uploads')
    MODEL_SAVE_PATH = os.path.join('savemodels')
    DATASET_PATH = 'dataset'
    GROQ_API_KEY = os.environ.get('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')
