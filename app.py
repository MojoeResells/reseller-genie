from flask import Flask, render_template, request, send_file
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from io import BytesIO
import os

app = Flask(__name__)
DB_PATH = 'reseller_data.db'

@app.route('/', methods=['GET', 'POST'])
def index():
    report = None
    chart_url = None
    error = None

    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        platform = request.form.get('platform', '').strip().lower()

        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql_query("SELECT * FROM inventory", conn)
            conn.close()

            df['date_sold'] = pd.to_datetime(df['date_sold'], errors='coerce')
            df = df.dropna(subset=['date_sold'])
            df['profit'] = df['sold_price'] - df['cost'] - df['fees']

            if start_date:
                df = df[df['date_sold'] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df['date_sold'] <= pd.to_datetime(end_date)]
            if platform:
                df = df[df['platform'].str.lower() == platform]

            total_sales = df['sold_price'].sum()
            total_profit = df['profit'].sum()
            total_items = len(df)
            avg_profit = df['profit'].mean() if total_items > 0 else 0
            tax_paid = df['tax'].sum() if 'tax' in df.columns else 0

            monthly = df.groupby(df['date_sold'].dt.to_period('M')).agg({
                'sold_price': 'sum',
                'profit': 'sum',
                'item_name': 'count'
            }).rename(columns={
                'sold_price': 'Sales',
                'profit': 'Profit',
                'item_name': 'Items'
            })

            chart_url = create_bar_chart(monthly)

            report = {
                'start': start_date or 'Start',
                'end': end_date or 'Now',
                'platform': platform or 'All',
                'items': total_items,
                'sales': total_sales,
                'profit': total_profit,
                'avg': avg_profit,
                'tax': tax_paid,
                'monthly': monthly.reset_index().astype(str).values.tolist()
            }

            df.to_csv('last_report.csv', index=False)

        except Exception as e:
            error = str(e)

    return render_template('index.html', report=report, chart_url=chart_url, error=error)

@app.route('/download')
def download_csv():
    if os.path.exists('last_report.csv'):
        return send_file('last_report.csv', as_attachment=True)
    return 'No report generated yet.'

def create_bar_chart(summary_df):
    fig, ax = plt.subplots(figsize=(6, 4))
    summary_df['Profit'].plot(kind='bar', ax=ax, title='Monthly Profit')
    ax.set_ylabel('Profit ($)')
    ax.set_xlabel('Month')
    fig.tight_layout()

    img = BytesIO()
    fig.savefig(img, format='png')
    img.seek(0)
    import base64
    base64_img = f"data:image/png;base64,{base64.b64encode(img.read()).decode()}"
    return base64_img

if __name__ == '__main__':
    app.run(debug=True)
