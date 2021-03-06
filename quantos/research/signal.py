# encoding: utf-8

import os

import numpy as np
import pandas as pd

from quantos.data.dataview import DataView
from quantos.data.dataservice import RemoteDataService
from quantos.research import alphalens
from quantos.util import fileio


def save_dataview():
    # total 130 seconds
    
    ds = RemoteDataService()
    dv = DataView()
    
    props = {'start_date': 20141114, 'end_date': 20170327, 'universe': '000300.SH',
             # 'symbol': 'rb1710.SHF,rb1801.SHF',
             'fields': ('open,high,low,close,vwap,volume,turnover,'
                        # + 'pb,net_assets,'
                        + 'total_oper_rev,oper_exp,tot_profit,int_income'
                        ),
             'freq': 1}
    
    dv.init_from_config(props, ds)
    dv.prepare_data()
    
    factor_formula = '-1 * Rank(Ts_Max(Delta(vwap, 7), 11))'  # GTJA
    factor_name = 'gtja'
    dv.add_formula(factor_name, factor_formula)
    dv.add_formula('eps_ret_wrong', 'Return(eps, 3)', is_quarterly=False)
    tmp = dv.get_ts('eps_ret_wrong')
    dv.add_formula('eps_ret', 'Return(eps, 3)', is_quarterly=True)
    tmp = dv.get_ts('eps_ret')
    
    
    dv.add_formula('look_ahead', 'Delay(Return(close_adj, 5), -5)')
    dv.add_formula('ret1', 'Return(close_adj, 1)')
    dv.add_formula('ret20', 'Delay(Return(close_adj, 20), -20)')
    
    dv.save_dataview(folder_path=fileio.join_relative_path('../output/prepared'))


def main():
    dv = DataView()
    
    fullpath = fileio.join_relative_path('../output/prepared/20141114_20170327_freq=1D')
    dv.load_dataview(folder=fullpath)
    print dv.fields

    factor_formula = '-1 * Rank(Ts_Max(Delta(vwap, 7), 11))'  # GTJA
    # factor_formula = '-Delta((((close - low) - (high - close)) / (high - low)), 1)'
    # factor_formula = '-Delta(close, 5) / close'#  / pb'  # revert
    # factor_formula = 'Delta(tot_profit, 1) / Delay(tot_profit, 1)' # pct change
    # factor_formula = '- Delta(close, 3) / Delay(close, 3)'
    # factor_formula = 'Delay(total_oper_rev, 1)'
    factor_name = 'factor1'
    # dv.add_formula(factor_name, factor_formula)

    # dv.add_formula('factor2', 'GroupApply(Standardize, GroupApply(Cutoff, gtja, 3.0))')
    # dv.add_formula('factor_bool', 'If(factor1 > total_oper_rev, 1.5, 0.5)')
    # dv.add_formula('factor2', 'Standardize(factor1)')
    
    factor = dv.get_ts('ret20').shift(1, axis=0)  # avoid look-ahead bias
    # factor = dv.get_ts('gtja').shift(1, axis=0)  # avoid look-ahead bias
    
    price = dv.get_ts('vwap')
    price_bench = dv._data_benchmark
    
    trade_status = dv.get_ts('trade_status')
    mask_sus = trade_status != u'交易'.encode('utf-8')

    df_group = dv.data_group.copy()
    from quantos.util import dtutil
    df_group.index = dtutil.convert_int_to_datetime(df_group.index)
    factor_data = alphalens.utils.get_clean_factor_and_forward_returns(factor, price,
                                                                       mask_sus=mask_sus, benchmark_price=None,
                                                                       quantiles=5, periods=[20],
                                                                       # groupby=df_group.stack(), by_group=False
                                                                       )
    res = alphalens.tears.create_full_tear_sheet(factor_data, long_short=True,
                                                 output_format='pdf', verbose=True,
                                                 # by_group=True
                                                 )
    # print res


def _test_append_custom_data():
    # --------------------------------------------------------------------------------
    # get custom data
    ds = RemoteDataService()
    # lb.blablabla
    df_raw, msg = ds.api.query("lb.secRestricted",
                                  fields="symbol,list_date,lifted_shares,lifted_ratio",
                                  filter="start_date=20170325&end_date=20170525",
                                  orderby="",
                                  data_format='pandas')
    assert msg == '0,'
    gp = df_raw.groupby(by=['list_date', 'symbol'])
    df_multi = gp.agg({'lifted_ratio': np.sum})
    
    df_value = df_multi.unstack(level=1)
    df_value.columns = df_value.columns.droplevel(level=0)
    
    # df_value = df_value.fillna(0.0)
    
    # --------------------------------------------------------------------------------
    # Format df_custom

    dv = DataView()
    dv.load_dataview('../output/prepared/20160609_20170601_freq=1D')
    
    df_value = df_value.loc[:, dv.symbol]
    df_custom = pd.DataFrame(index=dv.dates, columns=dv.symbol, data=None)
    df_custom.loc[df_value.index, df_value.columns] = df_value
    df_custom.fillna(0.0, inplace=True)
    
    # --------------------------------------------------------------------------------
    # append DataFrame to existed DataView
    dv.append_df(df_custom + 1e-3 * np.random.rand(df_custom.shape[1]), field_name='custom')
    dv.add_formula('myfactor', 'Rank(custom)')
    
    # --------------------------------------------------------------------------------
    # test this factor
    factor = dv.get_ts('myfactor')
    trade_status = dv.get_ts('trade_status')
    close = dv.get_ts('close')

    mask_sus = trade_status != u'交易'.encode('utf-8')

    factor_data = alphalens.utils.get_clean_factor_and_forward_returns(factor, close, mask_sus=mask_sus, periods=[5])

    alphalens.tears.create_full_tear_sheet(factor_data, output_format='pdf')
    
    
if __name__ == "__main__":
    from quantos.util.profile import SimpleTimer
    timer = SimpleTimer()
    timer.tick('start')

    timer.tick('import alphalens')
    save_dataview()
    # main()
    # test_append_custom_data()
    
    timer.tick('end')
