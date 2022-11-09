//
// Created by zhangjia17 on 2022/10/26.
//

#ifndef NGTCP2_NGTCP2_BWESTIMATE_H
#define NGTCP2_NGTCP2_BWESTIMATE_H

#include <ngtcp2/ngtcp2.h>
#include "ngtcp2_conn.h"
#include "ngtcp2_window_filter.h"

void ngtcp2_bwest_init(ngtcp2_conn *conn, ngtcp2_bw_estimate *bwest,
                       ngtcp2_log *log);
void ngtcp2_bwest_init_bbr(ngtcp2_bw_estimate *bwest);
void ngtcp2_bwest_init_westwood(ngtcp2_bw_estimate *bwest);
void ngtcp2_bwest_init_gcbe(ngtcp2_bw_estimate *bwest);
void ngtcp2_bwest_on_ack_recv(ngtcp2_bw_estimate *bwest,
                              ngtcp2_conn_stat *cstat, const ngtcp2_cc_ack *ack,
                              ngtcp2_tstamp ts);

void ngtcp2_bwest_on_ack_recv_bbr(ngtcp2_bw_estimate *bwest,
                                  ngtcp2_conn_stat *cstat);
void ngtcp2_bwest_on_ack_recv_westwood(ngtcp2_bw_estimate *bwest,
                                       ngtcp2_conn_stat *cstat,
                                       ngtcp2_tstamp ts,
                                       const ngtcp2_cc_ack *ack);
void ngtcp2_bwest_on_ack_recv_gcbe(ngtcp2_bw_estimate *bwest,
                                   ngtcp2_conn_stat *cstat, ngtcp2_tstamp ts,
                                   const ngtcp2_cc_ack *ack);
void update_smooth_btl_bw(ngtcp2_bw_estimate *bwest, uint64_t bw);
#endif // NGTCP2_NGTCP2_BWESTIMATE_H
