"""
可视化监控面板 - 从 relay_server 获取真实缓存统计
"""

import sys
sys.path.insert(0, 'H:\\GPU')

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pandas as pd

import dash
from dash import dcc, html, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

API_BASE = 'http://127.0.0.1:8001'


def _api(path: str, timeout: int = 2):
    try:
        import requests
        r = requests.get(f'{API_BASE}{path}', timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def create_app():
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True
    )
    app.title = "DeepSeek 缓存优化监控"

    app.layout = dbc.Container([
        dbc.Row([
            dbc.Col(html.H2("DeepSeek 缓存优化监控面板", className="text-center my-3"), width=12)
        ]),

        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("缓存命中率"),
                dbc.CardBody(html.H3(id="hit-rate-card", className="text-center text-success"))
            ]), width=3),
            dbc.Col(dbc.Card([
                dbc.CardHeader("缓存命中次数"),
                dbc.CardBody(html.H3(id="cache-hits-card", className="text-center"))
            ]), width=3),
            dbc.Col(dbc.Card([
                dbc.CardHeader("节省 Token"),
                dbc.CardBody(html.H3(id="tokens-saved-card", className="text-center text-info"))
            ]), width=3),
            dbc.Col(dbc.Card([
                dbc.CardHeader("总请求数"),
                dbc.CardBody(html.H3(id="total-requests-card", className="text-center"))
            ]), width=3),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("命中率历史"),
                dbc.CardBody(dcc.Graph(id="hit-rate-chart"))
            ]), width=6),
            dbc.Col(dbc.Card([
                dbc.CardHeader("响应时间对比 (ms)"),
                dbc.CardBody(dcc.Graph(id="response-time-chart"))
            ]), width=6),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("缓存层级命中分布"),
                dbc.CardBody(dcc.Graph(id="cache-levels-chart"))
            ]), width=4),
            dbc.Col(dbc.Card([
                dbc.CardHeader("请求类型分布"),
                dbc.CardBody(dcc.Graph(id="request-type-chart"))
            ]), width=4),
            dbc.Col(dbc.Card([
                dbc.CardHeader("热点查询 Top 10"),
                dbc.CardBody(
                    html.Div(id="hot-queries-table", style={'maxHeight': '300px', 'overflowY': 'auto'})
                )
            ]), width=4),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.Span("缓存大小: "),
                    html.Strong(id="cache-size-text", children="0"),
                    html.Span("  |  "),
                    html.Span("最后更新: "),
                    html.Strong(id="last-update-text", children="-"),
                ])
            ]), width=12)
        ]),

        dcc.Interval(id='interval', interval=5000)
    ], fluid=True)

    @callback(
        [Output("hit-rate-card", "children"),
         Output("hit-rate-card", "className"),
         Output("cache-hits-card", "children"),
         Output("tokens-saved-card", "children"),
         Output("total-requests-card", "children"),
         Output("cache-size-text", "children"),
         Output("last-update-text", "children")],
        Input("interval", "n_intervals")
    )
    def update_cards(_):
        m = _api('/api/metrics')
        hr = round(m.get('hit_rate', 0) * 100, 1)
        cls = "text-center text-success" if hr >= 50 else ("text-center text-warning" if hr >= 20 else "text-center text-danger")
        return (
            f"{hr}%",
            cls,
            f"{m.get('cache_hits', 0)}",
            f"{m.get('tokens_saved', 0)}",
            f"{m.get('total_requests', 0)}",
            f"{m.get('semantic_cache_size', 0)}",
            datetime.now().strftime('%H:%M:%S')
        )

    @callback(
        Output("hit-rate-chart", "figure"),
        Input("interval", "n_intervals")
    )
    def update_hit_rate_chart(_):
        h = _api('/api/history', timeout=3)
        if not h or not h.get('timestamps'):
            return px.line(title="命中率历史 (暂无数据)")

        df = pd.DataFrame({
            'timestamp': pd.to_datetime(h['timestamps']),
            'hit_rate': [v * 100 for v in h.get('hit_rates', [])]
        })
        if len(df) < 2:
            return px.line(df, x='timestamp', y='hit_rate', title="命中率历史 (%)")

        fig = px.line(df, x='timestamp', y='hit_rate', title="命中率历史 (%)")
        fig.add_hline(y=50, line_dash="dash", line_color="orange", annotation_text="50%")
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        return fig

    @callback(
        Output("response-time-chart", "figure"),
        Input("interval", "n_intervals")
    )
    def update_response_time_chart(_):
        m = _api('/api/metrics')
        hit_time = m.get('cache_hit_time', 0)
        miss_time = m.get('cache_miss_time', 0)
        avg_time = m.get('avg_response_time', 0)

        if not hit_time and not miss_time:
            return px.bar(title="响应时间对比 (暂无数据)")

        fig = go.Figure(data=[
            go.Bar(name='缓存命中', x=['响应时间'], y=[hit_time], marker_color='#28a745',
                   text=[f'{hit_time:.0f}ms'], textposition='auto'),
            go.Bar(name='缓存未命中', x=['响应时间'], y=[miss_time], marker_color='#dc3545',
                   text=[f'{miss_time:.0f}ms'], textposition='auto'),
            go.Bar(name='平均', x=['响应时间'], y=[avg_time], marker_color='#6c757d',
                   text=[f'{avg_time:.0f}ms'], textposition='auto'),
        ])
        fig.update_layout(barmode='group', margin=dict(l=20, r=20, t=40, b=20),
                          title="缓存命中 vs 未命中 响应时间 (ms)")
        return fig

    @callback(
        Output("cache-levels-chart", "figure"),
        Input("interval", "n_intervals")
    )
    def update_cache_levels(_):
        l = _api('/api/cache-levels')
        l1 = l.get('l1_hits', 0)
        l2 = l.get('l2_hits', 0)
        l3 = l.get('l3_hits', 0)

        if not l1 and not l2 and not l3:
            return px.pie(title="缓存层级分布 (暂无数据)")

        fig = go.Figure(data=[go.Pie(
            labels=['L1 精确', 'L2 SQLite', 'L3 文件'],
            values=[l1, l2, l3],
            marker_colors=['#17a2b8', '#ffc107', '#28a745'],
            hole=0.3
        )])
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        return fig

    @callback(
        Output("request-type-chart", "figure"),
        Input("interval", "n_intervals")
    )
    def update_request_type(_):
        m = _api('/api/metrics')
        types = {
            '代码生成': m.get('code_generation', 0),
            '代码解释': m.get('code_explanation', 0),
            '调试': m.get('debugging', 0),
            '一般问答': m.get('general_qa', 0),
            '对话': m.get('conversation', 0),
        }
        vals = [v for v in types.values() if v > 0]
        if not vals:
            return px.pie(title="请求类型分布 (暂无数据)")

        fig = go.Figure(data=[go.Pie(
            labels=list(types.keys()), values=list(types.values()),
            hole=0.3,
            marker_colors=['#007bff', '#6f42c1', '#e83e8c', '#fd7e14', '#20c997'],
        )])
        fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
        return fig

    @callback(
        Output("hot-queries-table", "children"),
        Input("interval", "n_intervals")
    )
    def update_hot_queries(_):
        queries = _api('/api/hot-queries')
        if not queries:
            return html.P("暂无热点查询数据", className="text-muted")

        rows = []
        for i, q in enumerate(queries[:10], 1):
            query_text = q.get('query', '')[:60]
            hits = q.get('hit_count', 0)
            rows.append(html.Tr([
                html.Td(f"{i}", style={'width': '30px'}),
                html.Td(query_text, style={'maxWidth': '200px', 'overflow': 'hidden', 'textOverflow': 'ellipsis', 'whiteSpace': 'nowrap'}),
                html.Td(f"{hits}"),
            ]))

        return dbc.Table([
            html.Thead(html.Tr([html.Th("#"), html.Th("查询"), html.Th("命中")])),
            html.Tbody(rows)
        ], size="sm", striped=True, bordered=False)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=8050, debug=False)
