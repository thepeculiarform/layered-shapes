from flask import Flask, jsonify, render_template
import sys

import polars as pl

app = Flask(__name__)

@app.route('/api/data')
def get_data():
    df = pl.read_json("E:/Projects/rjcd/rhino/layered_shapes/data.json")
    result = df.to_dicts()
    res = jsonify(result)
    res.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    res.headers['Pragma'] = 'no-cache'
    res.headers['Expires'] = '0'
    return res

@app.route('/')
def index():
    df = pl.read_json("E:/Projects/rjcd/rhino/layered_shapes/data.json")
    data = df.to_dicts()
    return render_template('index.html', data=data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)