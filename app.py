import os
import random
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from config import Config
from utils.db import get_db_connection
from auth import auth_bp
from groq_ai.analysis import get_breath_analysis_explanation
import sqlite3

app = Flask(__name__)
app.config.from_object(Config)

# Create upload folder if not exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Register Blueprints
app.register_blueprint(auth_bp)

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    # Get stats
    dataset_stats = conn.execute('SELECT category, count FROM dataset_stats').fetchall()
    model_stats = conn.execute('SELECT * FROM models ORDER BY created_at DESC LIMIT 5').fetchall()
    conn.close()
    
    # If no stats yet, use defaults
    if not dataset_stats:
        dataset_stats = [
            {'category': 'Benign', 'count': 120},
            {'category': 'Malignant', 'count': 85},
            {'category': 'Normal', 'count': 150}
        ]
    
    return render_template('dashboard.html', dataset_stats=dataset_stats, model_stats=model_stats)

@app.route('/dataset')
def view_dataset():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    view_all = request.args.get('view_all')
    categories = ['Bengin', 'Malignant', 'Normal']
    dataset_path = Config.DATASET_PATH
    
    data = {}
    for cat in categories:
        if view_all and view_all != cat:
            continue
            
        path = os.path.join(dataset_path, cat + ' cases')
        if os.path.exists(path):
            files = os.listdir(path)
            if view_all == cat:
                data[cat] = files # Show all
            else:
                data[cat] = files[:10] # Show first 10
        else:
            data[cat] = []
            
    return render_template('dataset.html', data=data, view_all=view_all)

@app.route('/dataset/<path:filename>')
def serve_dataset(filename):
    return send_from_directory(Config.DATASET_PATH, filename)

@app.route('/train', methods=['GET', 'POST'])
def train_models():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        from models.train import train_ensemble
        try:
            train_ensemble()
            flash('Ensemble models trained and optimized successfully!', 'success')
        except Exception as e:
            flash(f'Error during training: {str(e)}', 'error')
        return redirect(url_for('train_models'))
        
    return render_template('train.html')

@app.route('/test', methods=['GET', 'POST'])
def test_image():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)
        
        if file:
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Predict
            from models.inference import predict_lung_cancer
            result, confidence, voc_percentage = predict_lung_cancer(filepath)
            
            explanation = get_breath_analysis_explanation(result, confidence, voc_percentage)
            
            advice_map = {
                'Benign': 'No immediate threat detected. Maintain a healthy lifestyle and periodic check-ups.',
                'Malignant': 'High risk detected. Immediate consultation with an oncologist and further clinical tests (CT/Biopsy) are strongly advised.',
                'Normal': 'Biomarker levels are within the normal range. Continue regular health screenings.'
            }
            advice = advice_map.get(result)
            
            # Save to history
            conn = get_db_connection()
            conn.execute('''
                INSERT INTO predictions (filename, result, confidence, voc_percentage, explanation, advice)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (filename, result, confidence, voc_percentage, explanation, advice))
            conn.commit()
            conn.close()
            
            return redirect(url_for('prediction_result', filename=filename))
            
    return render_template('test.html')

@app.route('/result/<filename>')
def prediction_result(filename):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    result_data = conn.execute('SELECT * FROM predictions WHERE filename = ? ORDER BY created_at DESC', (filename,)).fetchone()
    conn.close()
    
    if not result_data:
        flash('Result not found', 'error')
        return redirect(url_for('test_image'))
    
    return render_template('result.html', result=result_data)

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db_connection()
    predictions = conn.execute('SELECT * FROM predictions ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('history.html', predictions=predictions)

if __name__ == '__main__':
    app.run(debug=False)
