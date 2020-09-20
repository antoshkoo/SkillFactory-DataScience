import pandas as pd
from typing import List, Union
import random
import plotly.express as px
import plotly.graph_objects as go

# dash specific imports
import dash_core_components as dcc
import dash_html_components as html
import dash.dependencies
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

PLOTLY_THEME = 'simple_white'


def stringify(x: Union[str, int]) -> str:
    return "'"+str(x)+"'"


# constants and needed options
data = pd.read_csv('data/staging_data_cleaned.csv')
statuses = data['status'].unique()
dates = data['date'].unique()
customer_ids = data['customer_id'].unique()

print(data.head())

# components
controls = dbc.Card(
    [

        dbc.FormGroup(
            [
                dbc.Label("Transaction status", id='status-selector-header'),
                dcc.Dropdown(
                    id="status-selector",
                    options=[{"label": col, "value": col} for col in statuses],
                    value="Paid",
                ),
                dbc.Tooltip('Select status to drill into statistics.', target="status-selector-header"),

            ]
        ),
        dbc.FormGroup(
            [
                dbc.Label("Customer ID", id='customer-id-selector-header'),
                dcc.Dropdown(
                    id="customer-id-selector",
                    options=[{"label": col, "value": col} for col in customer_ids],
                    value="", multi=True
                ),
                dbc.Tooltip('Multiple selection of customers makes it possible to track a set of customers over time.'
                            , target="customer-id-selector-header"),
            ]
        ),
        # dbc.FormGroup(
        #     [
        #         dbc.Label("Disputed or not "),
        #         dcc.Dropdown(
        #             id="disputes-selector",
        #             options=[{"label": col, "value": col} for col in data['customer_id'].unique()],
        #             value="Not disputed",
        #         ),
        #     ]
        # ),
        html.Div(id='params-store', style={'display': 'none'}),
        dcc.Store(id='data-store', data=data.to_dict('records')),
    ],
    body=True,
)

qty_graph = dcc.Graph(id='qty-graph')
time_graph = dcc.Graph(id='time-graph')


# dash app run
app = dash.Dash(name='staging_dashboard_refactored', external_stylesheets=[dbc.themes.FLATLY])
server = app.server

# general layout
app.layout = dbc.Container(
    [
     html.H1(u"Наш новый дашборд"),
     html.Hr(),
     dbc.Row([dbc.Col(controls, width=2),
              dbc.Col(qty_graph, width=5),
              dbc.Tooltip('A basic count plot for unique registrations and customers by day.', target="qty-graph"),
              dbc.Col(time_graph, width=5),
              dbc.Tooltip('A basic distribution plot for unique registrations and customers.', target="time-graph"),
              ], align="center"),
    ], fluid=True
)


@app.callback(Output(component_id='params-store', component_property='children'),
              [Input(component_id='status-selector', component_property='value'),
               Input(component_id='customer-id-selector', component_property='value')])
def collect_params(status: str, ids: str):

    ids = ', '.join([stringify(i)for i in ids])
    params = status, ids
    return params


@app.callback(Output(component_id='qty-graph', component_property='figure'),
              [Input(component_id='params-store', component_property='children'),
               Input(component_id='data-store', component_property='data')])
def update_qty_graph(selected_params: List, df: pd.DataFrame):

    # introducting variables
    df = pd.DataFrame(df)
    global statuses
    status, customer_ids = selected_params
    status = 'Paid' if status == '' else status

    # filtering
    status_query = 'status in {status} '.format(status=stringify(status)) if status else ''
    customer_query = ' customer_id in ({customer_id})'.format(customer_id=customer_ids) if customer_ids != '' else ''

    if 0 not in (len(status_query), len(customer_query)):
        total_query = status_query + 'and' + customer_query
    else:
        total_query = status_query + customer_query

    cleaned = df.query(total_query) if total_query != '' else df

    # aggregations
    reservations = (cleaned.groupby('date')['reservation_id'].count()).reset_index()
    customer_cnt = (cleaned.groupby('date')['customer_id'].nunique()).reset_index()

    # plotting
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=reservations['date'].values,
                             y=reservations['reservation_id'].values,
                             fill=None,
                             mode='lines+markers',
                             name='reservations', line={'color': 'indigo'}))
    fig.add_trace(
        go.Scatter(x=customer_cnt['date'].values,
                   y=customer_cnt['customer_id'].values,
                   fill=None,
                   mode='lines+markers',
                   name='customers', line={'color': 'orange'}))

    fig.update_layout(template=PLOTLY_THEME, title_text="Count metrics by day", xaxis_title=u"date",
                      yaxis_title="qty", legend=dict(x=.8, y=.99))
    return fig

@app.callback(Output(component_id='time-graph', component_property='figure'),
              [Input(component_id='params-store', component_property='children'),
               Input(component_id='data-store', component_property='data')])
def update_time_graph(selected_params: List, df: pd.DataFrame):

    # introducing variables
    df = pd.DataFrame(df)
    global statuses
    status, customer_ids = selected_params
    status = 'Paid' if status == '' else status

    # # filtering
    # cleaned_df = df[df['status'] == status]

    # filtering
    status_query = 'status in {status} '.format(status=stringify(status)) if status else ''
    customer_query = ' customer_id in ({customer_id})'.format(customer_id=customer_ids) if customer_ids != '' else ''

    if 0 not in (len(status_query), len(customer_query)):
        total_query = status_query + 'and' + customer_query
    else:
        total_query = status_query + customer_query

    cleaned_df = df.query(total_query) if total_query != '' else df

    # aggregating for plots
    cleaned_df['hour'] = pd.to_datetime(cleaned_df['created_(utc)']).apply(lambda x: x.hour)

    slice = ['reservation_id', 'date', 'hour']
    hourly_reservations = cleaned_df[slice].sort_values(slice).drop_duplicates()['hour']

    slice = ['customer_id', 'date', 'hour']
    hourly_customers = cleaned_df[slice].sort_values(slice).drop_duplicates()['hour']

    # plotting
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=hourly_reservations.values, histnorm='probability', nbinsx=24,
                               name='reservations per hour'))
    fig.add_trace(go.Histogram(x=hourly_customers.values, histnorm='probability', nbinsx=24,
                               name='unique customers per hour'))

    fig.update_traces(opacity=0.75)

    fig.update_layout(template=PLOTLY_THEME, title_text="Hourly distributions", xaxis_title=u"date",
                      yaxis_title="perc.", barmode='overlay', legend=dict(x=.02, y=.99),
                      xaxis=dict(tickmode='linear', tick0=0, dtick=1)
                      )
    return fig

if __name__ == '__main__':
    app.run_server(debug=True, host='127.0.0.1', port=8886)



