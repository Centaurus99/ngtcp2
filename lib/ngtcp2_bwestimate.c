//
// Created by zhangjia17 on 2022/10/26.
//
#include "ngtcp2_bwestimate.h"
#include "ngtcp2_conn.h"
#include "ngtcp2_macro.h"
#include <stdio.h>
#define NGTCP2_BBR_BTL_BW_FILTERLEN 10
#define NGTCP2_WESTWOOD_RTT_MIN 50000000 // ns, probe RTT period
#define NGTCP2_WESTWOOD_BTL_BW_FILTERLEN (1 * NGTCP2_SECONDS)
#define BD_SMOOOTH_SIZE 5
#define SCUBIC2_PRINT_BW_EST

void ngtcp2_bwest_init(ngtcp2_conn *conn, ngtcp2_bw_estimate *bwest,
                       ngtcp2_log *log) {
  (void)conn;
  bwest->log = log;
  ngtcp2_bwest_init_bbr(bwest);
  ngtcp2_bwest_init_westwood(bwest);
  ngtcp2_bwest_init_gcbe(bwest);
}

void ngtcp2_bwest_init_bbr(ngtcp2_bw_estimate *bwest) {
  bwest->btl_bw = 0;
  bwest->max_btl_bw = 0;
  bwest->round_count = 0;
  bwest->max_round_count = 0;
  ngtcp2_window_filter_init(&bwest->btl_bw_filter, NGTCP2_BBR_BTL_BW_FILTERLEN);
  ngtcp2_window_filter_init(&bwest->max_btl_bw_filter,
                            NGTCP2_BBR_BTL_BW_FILTERLEN);
  ngtcp2_log_info(bwest->log, NGTCP2_LOG_EVENT_RCV, "bwest->btl_bw=%" PRIu64,
                  bwest->btl_bw);
}

void ngtcp2_bwest_init_westwood(ngtcp2_bw_estimate *bwest) {
  bwest->bw_est = 0;
  bwest->bw_ns_est = 0;
  bwest->bw_est_acked_data = 0;
  bwest->last_bw_est_time = 0;
  ngtcp2_window_filter_init(&bwest->max_bw_est_filter,
                            NGTCP2_WESTWOOD_BTL_BW_FILTERLEN);
  bwest->max_bw_est = 0;
  bwest->westwood_round_count = 0;
}

void ngtcp2_bwest_init_gcbe(ngtcp2_bw_estimate *bwest) {
  bwest->smooth_btl_bw_max = 0;
  bwest->circle_start_ts = 0;
  bwest->circle_end_ts = 0;
  bwest->circle_max_duration = 0;
  bwest->bytes_acked_sum = 0;
  bwest->bytes_to_drop = 0;
  for (size_t i = 0; i < BD_SMOOOTH_SIZE; ++i) {
    bwest->smooth_btl_bw[i] = 0;
  }
  bwest->gcbe_round_count = 0;
  ngtcp2_window_filter_init(&bwest->max_gcbe_bw_filter,
                            NGTCP2_WESTWOOD_BTL_BW_FILTERLEN);
  bwest->max_gcbe_bw = 0;
}

void ngtcp2_bwest_on_ack_recv(ngtcp2_bw_estimate *bwest,
                              ngtcp2_conn_stat *cstat, const ngtcp2_cc_ack *ack,
                              ngtcp2_tstamp ts) {
  /* BBR */
  ngtcp2_bwest_on_ack_recv_bbr(bwest, cstat);
  ngtcp2_bwest_on_ack_recv_westwood(bwest, cstat, ts, ack);
  ngtcp2_bwest_on_ack_recv_gcbe(bwest, cstat, ts, ack);

#ifdef SCUBIC2_PRINT_BW_EST
  fprintf(stderr,
          "-- BWEST: ts=%" PRIu64 " delivery_rate=%" PRIu64
          " BBR_btl_bw=%" PRIu64 " BBR_max_btl_bw=%" PRIu64
          " WestWood_bw_est=%" PRIu64 " WestWood_max_bw_est=%" PRIu64
          " GCBE_smooth_btl_bw_max=%" PRIu64 " GCBE_max_gcbe_bw=%" PRIu64
          " --\n",
          ts, cstat->delivery_rate_sec, bwest->btl_bw, bwest->max_btl_bw,
          bwest->bw_est, bwest->max_bw_est, bwest->smooth_btl_bw_max,
          bwest->max_gcbe_bw);
#endif

  ngtcp2_log_info(
      bwest->log, NGTCP2_LOG_EVENT_RCV,
      "delivery_rate=%" PRIu64 " BBR btl_bw=%" PRIu64 " max_btl_bw=%" PRIu64
      " westwood bw_est=%" PRIu64 " max_bw_est=%" PRIu64
      " gcbe smooth_btl_bw_max=%" PRIu64 " max_gcbe_bw=%" PRIu64,
      cstat->delivery_rate_sec, bwest->btl_bw, bwest->max_btl_bw, bwest->bw_est,
      bwest->max_bw_est, bwest->smooth_btl_bw_max, bwest->max_gcbe_bw);
}

void ngtcp2_bwest_on_ack_recv_bbr(ngtcp2_bw_estimate *bwest,
                                  ngtcp2_conn_stat *cstat) {
  /* bbr */
  ngtcp2_window_filter_update(&bwest->btl_bw_filter, cstat->delivery_rate_sec,
                              bwest->round_count);
  ++bwest->round_count;
  bwest->btl_bw = ngtcp2_window_filter_get_best(&bwest->btl_bw_filter);

  if (cstat->delivery_rate_sec < bwest->btl_bw) {
    return;
  }

  ngtcp2_window_filter_update(&bwest->max_btl_bw_filter,
                              cstat->delivery_rate_sec, bwest->max_round_count);
  ++bwest->max_round_count;
  bwest->max_btl_bw = ngtcp2_window_filter_get_best(&bwest->max_btl_bw_filter);
}

static uint64_t ngtcp2_bwest_westwood_do_filter(uint64_t a, uint64_t b) {
  return ((7 * a) + b) >> 3;
}

void ngtcp2_bwest_on_ack_recv_westwood(ngtcp2_bw_estimate *bwest,
                                       ngtcp2_conn_stat *cstat,
                                       ngtcp2_tstamp ts,
                                       const ngtcp2_cc_ack *ack) {
  /* westwood */
  ngtcp2_duration delta;

  if (bwest->last_bw_est_time == 0) {
    bwest->last_bw_est_time = ts;
    bwest->bw_est_acked_data = 0;
    return;
  }

  delta = ts - bwest->last_bw_est_time;

  bwest->bw_est_acked_data =
      bwest->bw_est_acked_data + ack->bytes_delivered + ack->bytes_lost;

  // renshaorui: change "smoothed_rtt" to max(lastest_rtt, 50ms)
  if (delta > ngtcp2_max(cstat->latest_rtt, NGTCP2_WESTWOOD_RTT_MIN)) {
    if (bwest->bw_ns_est == 0 && bwest->bw_est == 0) {
      bwest->bw_ns_est = bwest->bw_est_acked_data * NGTCP2_SECONDS / delta;
      bwest->bw_est = bwest->bw_ns_est;
    } else {
      bwest->bw_ns_est = ngtcp2_bwest_westwood_do_filter(
          bwest->bw_ns_est, bwest->bw_est_acked_data * NGTCP2_SECONDS / delta);
      bwest->bw_est =
          ngtcp2_bwest_westwood_do_filter(bwest->bw_est, bwest->bw_ns_est);
    }
    bwest->bw_est_acked_data = 0;
    bwest->last_bw_est_time = ts;
  }
  ngtcp2_window_filter_update(&bwest->max_bw_est_filter, bwest->bw_est, ts);
  ++bwest->westwood_round_count;
  bwest->max_bw_est = ngtcp2_window_filter_get_best(&bwest->max_bw_est_filter);
}

void update_smooth_btl_bw(ngtcp2_bw_estimate *bwest, uint64_t bw) {
  uint64_t max_bw = bw;
  for (size_t i = BD_SMOOOTH_SIZE - 1; i > 0; --i) {
    bwest->smooth_btl_bw[i] = bwest->smooth_btl_bw[i - 1];
    max_bw = ngtcp2_max(max_bw, bwest->smooth_btl_bw[i]);
  }
  bwest->smooth_btl_bw[0] = bw;
  bwest->smooth_btl_bw_max = max_bw;
}

void ngtcp2_bwest_on_ack_recv_gcbe(ngtcp2_bw_estimate *bwest,
                                   ngtcp2_conn_stat *cstat, ngtcp2_tstamp ts,
                                   const ngtcp2_cc_ack *ack) {
  if (bwest->circle_start_ts == 0) {
    bwest->circle_start_ts = ts;
    bwest->circle_end_ts = ts;
  }
  if (ts - bwest->circle_end_ts > bwest->circle_max_duration) {
    bwest->circle_max_duration = ts - bwest->circle_end_ts;
    bwest->bytes_to_drop = ack->bytes_delivered;
  }
  bwest->bytes_acked_sum += ack->bytes_delivered;
  bwest->circle_end_ts = ts;

  if (bwest->circle_end_ts - bwest->circle_start_ts >= cstat->smoothed_rtt) {
    if (bwest->circle_end_ts - bwest->circle_start_ts -
        bwest->circle_max_duration) {
      update_smooth_btl_bw(bwest,
                           (bwest->bytes_acked_sum - bwest->bytes_to_drop) *
                               NGTCP2_SECONDS /
                               (bwest->circle_end_ts - bwest->circle_start_ts -
                                bwest->circle_max_duration));
    } else {
      update_smooth_btl_bw(bwest,
                           bwest->bytes_acked_sum * NGTCP2_SECONDS /
                               (bwest->circle_end_ts - bwest->circle_start_ts));
    }
    bwest->bytes_acked_sum = 0;
    bwest->bytes_to_drop = 0;
    bwest->circle_start_ts = bwest->circle_end_ts;
    bwest->circle_max_duration = 0;
    ngtcp2_log_info(bwest->log, NGTCP2_LOG_EVENT_RCV,
                    "----- BTL_BW UPDATE; circle_start_ts=%" PRIu64
                    "; circle_end_ts=%" PRIu64 "; bytes_acked_sum=%" PRIu64
                    "; bytes_to_drop=%" PRIu64 "; circle_max_duration=%" PRIu64
                    "; current_bw=%" PRIu64,
                    bwest->circle_start_ts, bwest->circle_end_ts,
                    bwest->bytes_acked_sum, bwest->bytes_to_drop,
                    bwest->circle_max_duration, bwest->smooth_btl_bw[0]);
  }

  ngtcp2_window_filter_update(&bwest->max_gcbe_bw_filter,
                              bwest->smooth_btl_bw_max, ts);
  ++bwest->gcbe_round_count;
  bwest->max_gcbe_bw =
      ngtcp2_window_filter_get_best(&bwest->max_gcbe_bw_filter);
}
