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

# constants and needed options
data = pd.read_csv('data/staging_data_cleaned.csv')
statuses = data['status'].unique()
dates = data['date'].unique()
customer_ids = data['customer_id'].unique()

PLOTLY_THEME = 'simple_white'
N_SCOOTERS = pd.DataFrame(data=[random.randint(5, 10) for i in range(0, len(dates))], columns=['n_scooters'])


def stringify(x: Union[str, int]) -> str:
    return "'"+str(x)+"'"


# components
controls = dbc.Card(
    [
        dbc.FormGroup(
            [
                dbc.Label("Metric aggregation slice", id='slice-selector-header'),
                dcc.Dropdown(
                    id="slice-selector",
                    options=[{"label": 'Gross per day', "value": 'gross'},
                             {"label": 'Gross per scooter', "value": 'gross_scooter'},
                             {"label": 'Mean per day', "value": 'mean'},
                             {"label": 'Mean per scooter', "value": 'mean_scooter'}],
                    value="gross",
                ),
                dbc.Tooltip('Per scooter metrics are calculated with a help '
                            'of randomly generated vector of scooter quantity for each date point. '
                            'In real life count of scooter ids shall be used.',
                            target="slice-selector-header"),
            ]
        ),
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
                    value="", multi=True,
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
money_graph = dcc.Graph(id='raw-money-graph')
margin_graph = dcc.Graph(id='margin-graph')

# dash app run
app = dash.Dash(name='staging_dashboard', external_stylesheets=[dbc.themes.FLATLY])
server = app.server


# general layout
app.layout = dbc.Container(
    [
     html.H1("Staging data dashboard"),
     html.Hr(),
     dbc.Row([dbc.Col(controls, width=2),
              dbc.Col(qty_graph, width=5),
              dbc.Tooltip('A basic count plot for unique registrations and customers by day.', target="qty-graph"),
              dbc.Col(time_graph, width=5),
              dbc.Tooltip('A basic distribution plot for unique registrations and customers.', target="time-graph"),
              ], align="center"),
     dbc.Row([
              dbc.Col(money_graph, width=5),
              dbc.Tooltip('Green filled area is difference between holded funds, or in other words - revenue.'
                          'In cases when status is "Refunded" or "Failed" there is no revenue.',
                          target="raw-money-graph"),
              dbc.Col(margin_graph, width=5),
              dbc.Tooltip('Green filled area in this case is difference between revenue and fees,  '
                          'which results in margin. '
                          'In cases when status is "Refunded" or "Failed" mo margin is calculated.',
                          target="margin-graph"),
              ], align="right", justify="end")
    ], fluid=True
)


@app.callback(Output(component_id='params-store', component_property='children'),
              [Input(component_id='slice-selector', component_property='value'),
               Input(component_id='status-selector', component_property='value'),
               Input(component_id='customer-id-selector', component_property='value')])
def collect_params(slice: str, status: str, customer_ids: str):

    customer_ids = ', '.join([stringify(i)for i in customer_ids])
    params = slice, status, customer_ids
    return params


@app.callback(Output(component_id='time-graph', component_property='figure'),
              [Input(component_id='params-store', component_property='children'),
               Input(component_id='data-store', component_property='data')])
def update_time_graph(selected_params: List, df: pd.DataFrame):

    df = pd.DataFrame(df)
    global statuses
    slice, status, customer_ids = selected_params
    status = 'Paid' if status == '' else status
    cleaned_df = df[df['status'] == status]

    cleaned_df['hour'] = pd.to_datetime(cleaned_df['created_(utc)']).apply(lambda x: x.hour)

    hourly_reservations = cleaned_df[['reservation_id', 'date', 'hour']].sort_values(
        ['reservation_id', 'date', 'hour']).drop_duplicates()['hour']

    hourly_customers = cleaned_df[['customer_id', 'date', 'hour']].sort_values(
        ['customer_id', 'date', 'hour']).drop_duplicates()['hour']

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


@app.callback(Output(component_id='qty-graph', component_property='figure'),
              [Input(component_id='params-store', component_property='children'),
               Input(component_id='data-store', component_property='data')])
def update_qty_graph(selected_params: List, df: pd.DataFrame):

    df = pd.DataFrame(df)
    global statuses
    slice, status, customer_ids = selected_params

    status = 'Paid' if status == '' else status
    status_query = 'status in {status} '.format(status=stringify(status)) if status else ''
    customer_query = ' customer_id in ({customer_id})'.format(customer_id=customer_ids) if customer_ids != '' else ''

    if 0 not in (len(status_query), len(customer_query)):
        total_query = status_query + 'and' + customer_query
    else:
        total_query = status_query + customer_query

    cleaned = df.query(total_query) if total_query != '' else df
    reservations = (cleaned.groupby('date')['reservation_id'].count()).reset_index()
    customer_cnt = (cleaned.groupby('date')['customer_id'].nunique()).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=reservations['date'].values, y=reservations['reservation_id'].values, fill=None, mode='lines+markers',
                             name='reservations', line={'color': 'indigo'}))
    fig.add_trace(
        go.Scatter(x=customer_cnt['date'].values, y=customer_cnt['customer_id'].values, fill=None, mode='lines+markers',
                   name='customers', line={'color': 'orange'}))

    fig.update_layout(template=PLOTLY_THEME, title_text="Count metrics by day", xaxis_title=u"date",
                      yaxis_title="qty", legend=dict(x=.8, y=.99))
    return fig


@app.callback(Output(component_id='raw-money-graph', component_property='figure'),
              [Input(component_id='params-store', component_property='children'),
               Input(component_id='data-store', component_property='data')])
def update_raw_money_graph(selected_params: List, df: pd.DataFrame):

    df = pd.DataFrame(df)
    slice, status, customer_ids = selected_params

    global statuses

    status = 'Paid' if status == '' else status
    revenue_filler = 'tonexty' if status == 'Paid' else None
    status_query = 'status in {status} '.format(status=stringify(status)) if status else ''
    customer_query = ' customer_id in ({customer_id})'.format(customer_id=customer_ids) if customer_ids != '' else ''

    if 0 not in (len(status_query), len(customer_query)):
        total_query = status_query + 'and' + customer_query
    else:
        total_query = status_query + customer_query

    cleaned_df = df.query(total_query) if total_query != '' else df

    if 'mean' in slice:
        fees = cleaned_df.groupby('date')['fee'].mean().reset_index()
        refunds = cleaned_df.groupby('date')['amount_refunded'].mean().reset_index()
        hold = cleaned_df.groupby('date')['amount'].mean().reset_index()

        df = fees.merge(refunds, on='date', how='inner').merge(hold, on='date', how='inner')

        if slice == 'mean':
            fig = go.Figure()
            fig.update_layout(yaxis_title="$, mean")

        elif slice == 'mean_scooter':
            df = (pd.concat([df, N_SCOOTERS], axis=1)).set_index('date')
            df = (df[['fee', 'amount_refunded', 'amount']].div(df['n_scooters'], axis=0)).reset_index()

            fig = go.Figure()
            fig.update_layout(yaxis_title="$ per scooter, mean")

    elif 'gross' in slice:
        fees = cleaned_df.groupby('date')['fee'].sum().reset_index()
        refunds = cleaned_df.groupby('date')['amount_refunded'].sum().reset_index()
        hold = cleaned_df.groupby('date')['amount'].sum().reset_index()

        df = fees.merge(refunds, on='date', how='inner').merge(hold, on='date', how='inner')

        if slice == 'gross':
            fig = go.Figure()
            fig.update_layout(yaxis_title="$, gross")

        elif slice == 'gross_scooter':
            df = (pd.concat([df, N_SCOOTERS], axis=1)).set_index('date')
            df = (df[['fee', 'amount_refunded', 'amount']].div(df['n_scooters'], axis=0)).reset_index()

            fig = go.Figure()
            fig.update_layout(yaxis_title="$ per scooter, gross")
    else:
        fig = go.Figure()

    # if 'gross' in slice:
    #     fees = cleaned_df.groupby('date')['fee'].sum().reset_index()
    #     refunds = cleaned_df.groupby('date')['amount_refunded'].sum().reset_index()
    #     revenue = cleaned_df.groupby('date')['revenue'].sum().reset_index()
    #
    # if slice == 'gross':
    #
    #     fees = cleaned_df.groupby('date')['fee'].sum().reset_index()
    #     refunds = cleaned_df.groupby('date')['amount_refunded'].sum().reset_index()
    #     revenue = cleaned_df.groupby('date')['revenue'].sum().reset_index()
    #
    #     df = fees.merge(refunds, on='date', how='inner').merge(revenue, on='date', how='inner')
    #     fig = go.Figure()
    #     fig.update_layout(yaxis_title="$, gross")
    #
    # elif slice == 'mean':
    #
    #     fees = cleaned_df.groupby('date')['fee'].mean().reset_index()
    #     refunds = cleaned_df.groupby('date')['amount_refunded'].mean().reset_index()
    #     revenue = cleaned_df.groupby('date')['revenue'].mean().reset_index()
    #
    #     df = fees.merge(refunds, on='date', how='inner').merge(revenue, on='date', how='inner')
    #     fig = go.Figure()
    #     fig.update_layout(yaxis_title="$, gross")
    #
    # elif slice == 'scooter_mean':
    #     df = fees.merge(refunds, on='date', how='inner').merge(revenue, on='date', how='inner')
    #     df = (pd.concat([df, N_SCOOTERS], axis=1)).set_index('date')
    #     df = (df[['fee', 'amount_refunded', 'revenue']].div(df['n_scooters'], axis=0)).reset_index()
    #
    #     fig = go.Figure()
    #     fig.update_layout(yaxis_title="$, per scooter")

    # adding lines on figure

    fig.add_trace(go.Scatter(x=df['date'].values, y=df['fee'].values, fill=None, mode='lines+markers',
                             name='fees', line={'color': 'orange'}))

    fig.add_trace(go.Scatter(x=df['date'].values, y=df['amount_refunded'].values, fill=None, mode='lines+markers',
                             name='amount_refunded', line={'color': 'tomato'}))

    fig.add_trace(go.Scatter(x=df['date'].values, y=df['amount'].values, fill=revenue_filler, mode='lines+markers',
                             name='on hold', line={'color': 'green'}))

    fig.update_yaxes(tick0=-0.5)

    fig.update_layout(template=PLOTLY_THEME, title_text="Raw money streams by day", xaxis_title=u"date")

    return fig


@app.callback(Output(component_id='margin-graph', component_property='figure'),
              [Input(component_id='params-store', component_property='children'),
               Input(component_id='data-store', component_property='data')])
def update_margin_graph(selected_params: List, df: pd.DataFrame):

    df = pd.DataFrame(df)
    slice, status, customer_ids = selected_params

    global statuses

    if status == 'Paid' or '':

        status_query = 'status in {status} '.format(status=stringify(status))
        customer_query = ' customer_id in ({customer_id})'.format(customer_id=customer_ids) if customer_ids != '' else ''

        if 0 not in (len(status_query), len(customer_query)):
            total_query = status_query + 'and' + customer_query
        else:
            total_query = status_query + customer_query

        cleaned_df = df.query(total_query) if total_query != '' else df
        cleaned_df['revenue'] = cleaned_df['amount'] - cleaned_df['amount_refunded']

        groupped = (cleaned_df.groupby('date')[['fee', 'revenue']].sum()).reset_index()

        if 'mean' in slice:

            if slice == 'mean':
                fig = go.Figure()
                fig.update_layout(yaxis_title="$, mean")

            elif slice == 'mean_scooter':
                groupped = (pd.concat([groupped, N_SCOOTERS], axis=1)).set_index('date')
                groupped = (groupped[['fee', 'revenue']].div(groupped['n_scooters'], axis=0)).reset_index()

                fig = go.Figure()
                fig.update_layout(yaxis_title="$ per scooter, mean")

        elif 'gross' in slice:

            if slice == 'gross':
                fig = go.Figure()
                fig.update_layout(yaxis_title="$, gross")

            elif slice == 'gross_scooter':
                groupped = (pd.concat([groupped, N_SCOOTERS], axis=1)).set_index('date')
                groupped = (groupped[['fee', 'revenue']].div(groupped['n_scooters'], axis=0)).reset_index()

                fig = go.Figure()
                fig.update_layout(yaxis_title="$ per scooter, gross")

        fig.add_trace(go.Scatter(x=groupped['date'].values, y=groupped['fee'].values, fill=None, mode='lines+markers',
                                 name='fees', line={'color': 'yellow'}))
        fig.add_trace(go.Scatter(x=groupped['date'].values, y=groupped['revenue'].values, fill='tonexty', mode='lines+markers',
                                 name='revenue', line={'color': 'green'}))

    else:
        fig = go.Figure()

    fig.update_yaxes(tick0=-0.5)
    fig.update_layout(template=PLOTLY_THEME, title_text="Margin by day", xaxis_title=u"date")

    return fig


if __name__ == '__main__':
    app.run_server(debug=True, host='127.0.0.1', port=8887)
