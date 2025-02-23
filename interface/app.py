from flask import Flask, jsonify, render_template
import argparse

import polars as pl

import pathlib

path = pathlib.Path(__file__).resolve().parent
app = Flask(__name__)

@app.route('/api/data')
def get_data():
    data_path = str(path).split("interface")[0]
    df = pl.read_json(f"{data_path}/data.json")
    result = df.to_dicts()
    res = jsonify(result)
    res.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    res.headers['Pragma'] = 'no-cache'
    res.headers['Expires'] = '0'
    return res

@app.route('/')
def index():
    data_path = str(path).split("interface")[0]
    df = pl.read_json(f"{data_path}/data.json")
    data = df.to_dicts()
    return render_template('index.html', data=data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Flask app with a custom port.')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the app on (default: 5000)')
    args = parser.parse_args()

    app.run(host='0.0.0.0', port=args.port)