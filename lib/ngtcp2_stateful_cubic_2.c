
#include "ngtcp2_stateful_cubic_2.h"

#include <assert.h>
#include <stdio.h>
#include <arpa/inet.h>
#include <stdlib.h>

// #define SCUBIC2_PRINT_CC_LOG
// #define SCUBIC2_PRINT_ACK
// #define SCUBIC2_PRINT_RTT
// #define SCUBIC2_PRINT_SENT
#define FAKE_STATE

#if defined(_MSC_VER)
#  include <intrin.h>
#endif

#include "ngtcp2_log.h"
#include "ngtcp2_macro.h"
#include "ngtcp2_mem.h"
#include "ngtcp2_rcvry.h"

#define HASH_SIZE (1 << 10)
#define BD_SMOOOTH_SIZE 5
#define RTT_SAMPLE_SIZE 5

static ngtcp2_scubic2_state state_hashmap[HASH_SIZE];
static ngtcp2_scubic2_state *current_state;
static ngtcp2_scubic2_setup_phase setup_phase;
static uint64_t DRAIN_start_ts;

static size_t hash_address(const ngtcp2_sockaddr *sa) {
  size_t hash = 0;
  switch (sa->sa_family) {
  case AF_INET: {
    struct sockaddr_in *addr_in = (struct sockaddr_in *)sa;
    hash = addr_in->sin_addr.s_addr % HASH_SIZE;
    break;
  }
  default: {
    fprintf(stderr, "Unknown address family\n");
    break;
  }
  }
  return hash;
}

static int hash_init(ngtcp2_conn_stat *cstat, const ngtcp2_sockaddr *sa) {
  current_state = NULL;
  switch (sa->sa_family) {
  case AF_INET: {
    struct sockaddr_in *addr_in = (struct sockaddr_in *)sa;
    size_t hash = hash_address(sa);
    fprintf(stderr, "hash: %zu\n", hash);
    current_state = &state_hashmap[hash];
#ifdef FAKE_STATE
    current_state->address.s_addr = addr_in->sin_addr.s_addr;
    current_state->btl_bw = 3000000;
    current_state->min_rtt = 22000000;
#endif
    if (current_state->address.s_addr == addr_in->sin_addr.s_addr &&
        current_state->btl_bw != 0) {
      fprintf(stderr, "---------------- STATE  ACTIVE ----------------\n");
      fprintf(stderr,
              "----- STATE: btl_bw=%" PRIu64 "; min_rtt=%" PRIu64 "; -----\n",
              current_state->btl_bw, current_state->min_rtt);

      setup_phase = NGTCP2_SCUBIC2_SETUP_PHASE_INITIAL;
      cstat->cwnd =
          current_state->btl_bw * current_state->min_rtt / NGTCP2_SECONDS;
      cstat->pacing_rate = (double)current_state->btl_bw / NGTCP2_SECONDS;

      fprintf(stderr, "----- SET cwnd=%" PRIu64 " -----\n", cstat->cwnd);
      fprintf(stderr, "----- SET pacing_rate=%lf -----\n", cstat->pacing_rate);

    } else {
      fprintf(stderr, "--------------- STATE  INACTIVE ---------------\n");
      setup_phase = NGTCP2_SCUBIC2_SETUP_PHASE_END;
      current_state->address = addr_in->sin_addr;
    }
    current_state->btl_bw = 0;
    current_state->min_rtt = UINT64_MAX;
    return 0;
  }
  default: {
    fprintf(stderr, "Unknown address family\n");
    return 1;
  }
  }
}

static void straddr(const ngtcp2_sockaddr *sa) {
  char s[INET6_ADDRSTRLEN > INET_ADDRSTRLEN ? INET6_ADDRSTRLEN
                                            : INET_ADDRSTRLEN];
  switch (sa->sa_family) {
  case AF_INET: {
    struct sockaddr_in *addr_in = (struct sockaddr_in *)sa;
    inet_ntop(AF_INET, &(addr_in->sin_addr), s, INET_ADDRSTRLEN);
    break;
  }
  case AF_INET6: {
    struct sockaddr_in6 *addr_in6 = (struct sockaddr_in6 *)sa;
    inet_ntop(AF_INET6, &(addr_in6->sin6_addr), s, INET6_ADDRSTRLEN);
    break;
  }
  default: {
    fprintf(stderr, "Unknown address family\n");
    break;
  }
  }
  fprintf(stderr, "IP address: %s\n", s);
}

static ngtcp2_tstamp circle_start_ts, circle_end_ts;
static ngtcp2_duration circle_max_duration;
static uint64_t smooth_btl_bw[BD_SMOOOTH_SIZE], smooth_btl_bw_max;
static uint64_t bytes_acked_sum, bytes_to_drop;

static void init_smooth_btl_bw(void) {
  circle_start_ts = circle_end_ts = 0;
  circle_max_duration = 0;
  bytes_acked_sum = bytes_to_drop = smooth_btl_bw_max = 0;
  for (size_t i = 0; i < BD_SMOOOTH_SIZE; ++i) {
    smooth_btl_bw[i] = 0;
  }
}

static void update_smooth_btl_bw(uint64_t bw) {
  uint64_t max_bw = bw;
  for (size_t i = BD_SMOOOTH_SIZE - 1; i > 0; --i) {
    smooth_btl_bw[i] = smooth_btl_bw[i - 1];
    max_bw = ngtcp2_max(max_bw, smooth_btl_bw[i]);
  }
  smooth_btl_bw[0] = bw;
  smooth_btl_bw_max = max_bw;
}

static uint64_t smooth_btl_bw_on_ack_recv(ngtcp2_tstamp ts,
                                          uint64_t bytes_delivered,
                                          ngtcp2_conn_stat *cstat) {
  if (circle_start_ts == 0) {
    circle_start_ts = circle_end_ts = ts;
  }
  if (ts - circle_end_ts > circle_max_duration) {
    circle_max_duration = ts - circle_end_ts;
    bytes_to_drop = bytes_delivered;
  }
  bytes_acked_sum += bytes_delivered;
  circle_end_ts = ts;

  if (circle_end_ts - circle_start_ts >= cstat->smoothed_rtt) {

#ifdef SCUBIC2_PRINT_CC_LOG
    fprintf(stderr,
            "----- BTL_BW UPDATE; circle_start_ts=%" PRIu64
            "; circle_end_ts=%" PRIu64 "; bytes_acked_sum=%" PRIu64
            "; bytes_to_drop=%" PRIu64 "; circle_max_duration=%" PRIu64
            " -----\n",
            circle_start_ts, circle_end_ts, bytes_acked_sum, bytes_to_drop,
            circle_max_duration);
#endif

    if (bytes_acked_sum == bytes_to_drop) {
      update_smooth_btl_bw(bytes_acked_sum * NGTCP2_SECONDS /
                           (circle_end_ts - circle_start_ts));
    } else {
      update_smooth_btl_bw(
          (bytes_acked_sum - bytes_to_drop) * NGTCP2_SECONDS /
          (circle_end_ts - circle_start_ts - circle_max_duration));
    }
    bytes_acked_sum = bytes_to_drop = 0;
    circle_start_ts = circle_end_ts;
    circle_max_duration = 0;
  }

  return smooth_btl_bw_max;
}

static ngtcp2_rtt_sample rtt_samples[RTT_SAMPLE_SIZE];
static size_t rtt_sample_idx;

static void init_rtt_samples(void) { rtt_sample_idx = 0; }

static int in_congestion_recovery(const ngtcp2_conn_stat *cstat,
                                  ngtcp2_tstamp sent_time) {
  return cstat->congestion_recovery_start_ts != UINT64_MAX &&
         sent_time <= cstat->congestion_recovery_start_ts;
}

static void scubic2_cc_reset(ngtcp2_scubic2_cc *cc) {
  cc->max_delivery_rate_sec = 0;
  cc->target_cwnd = 0;
  cc->w_last_max = 0;
  cc->w_tcp = 0;
  cc->origin_point = 0;
  cc->epoch_start = UINT64_MAX;
  cc->k = 0;

  cc->prior.cwnd = 0;
  cc->prior.ssthresh = 0;
  cc->prior.w_last_max = 0;
  cc->prior.w_tcp = 0;
  cc->prior.origin_point = 0;
  cc->prior.epoch_start = UINT64_MAX;
  cc->prior.k = 0;

  cc->rtt_sample_count = 0;
  cc->current_round_min_rtt = UINT64_MAX;
  cc->last_round_min_rtt = UINT64_MAX;
  cc->window_end = -1;
}

void ngtcp2_scubic2_cc_init(ngtcp2_scubic2_cc *cc, ngtcp2_log *log) {
  cc->ccb.log = log;
  scubic2_cc_reset(cc);
}

void ngtcp2_scubic2_cc_free(ngtcp2_scubic2_cc *cc) { (void)cc; }

int ngtcp2_cc_scubic2_cc_init(ngtcp2_cc *cc, ngtcp2_log *log,
                              ngtcp2_conn_stat *cstat, const ngtcp2_mem *mem,
                              const ngtcp2_path *path) {
  ngtcp2_scubic2_cc *scubic2_cc;

  fprintf(stderr, "-------------------- START --------------------\n");
  straddr(path->remote.addr);
  hash_init(cstat, path->remote.addr);
  init_smooth_btl_bw();
  init_rtt_samples();

  scubic2_cc = ngtcp2_mem_calloc(mem, 1, sizeof(ngtcp2_scubic2_cc));
  if (scubic2_cc == NULL) {
    return NGTCP2_ERR_NOMEM;
  }

  ngtcp2_scubic2_cc_init(scubic2_cc, log);

  cc->ccb = &scubic2_cc->ccb;
  cc->on_pkt_acked = ngtcp2_cc_scubic2_cc_on_pkt_acked;
  cc->congestion_event = ngtcp2_cc_scubic2_cc_congestion_event;
  cc->on_spurious_congestion = ngtcp2_cc_scubic2_cc_on_spurious_congestion;
  cc->on_persistent_congestion = ngtcp2_cc_scubic2_cc_on_persistent_congestion;
  cc->on_ack_recv = ngtcp2_cc_scubic2_cc_on_ack_recv;
  cc->on_pkt_sent = ngtcp2_cc_scubic2_cc_on_pkt_sent;
  cc->new_rtt_sample = ngtcp2_cc_scubic2_cc_new_rtt_sample;
  cc->reset = ngtcp2_cc_scubic2_cc_reset;
  cc->event = ngtcp2_cc_scubic2_cc_event;

  return 0;
}

void ngtcp2_cc_scubic2_cc_free(ngtcp2_cc *cc, const ngtcp2_mem *mem) {
  ngtcp2_scubic2_cc *scubic2_cc =
      ngtcp2_struct_of(cc->ccb, ngtcp2_scubic2_cc, ccb);

  if (current_state != NULL) {
    fprintf(stderr,
            "----- FINAL STATE: btl_bw=%" PRIu64 "; min_rtt=%" PRIu64
            "; -----\n",
            current_state->btl_bw, current_state->min_rtt);
  }
  fprintf(stderr, "--------------------- END ---------------------\n");

  ngtcp2_scubic2_cc_free(scubic2_cc);
  ngtcp2_mem_free(mem, scubic2_cc);
}

static uint64_t ngtcp2_cbrt(uint64_t n) {
  int d;
  uint64_t a;

  if (n == 0) {
    return 0;
  }

#if defined(_MSC_VER)
#  if defined(_M_X64)
  d = (int)__lzcnt64(n);
#  elif defined(_M_ARM64)
  {
    unsigned long index;
    d = sizeof(uint64_t) * CHAR_BIT;
    if (_BitScanReverse64(&index, n)) {
      d = d - 1 - index;
    }
  }
#  else
  if ((n >> 32) != 0) {
    d = __lzcnt((unsigned int)(n >> 32));
  } else {
    d = 32 + __lzcnt((unsigned int)n);
  }
#  endif
#else
  d = __builtin_clzll(n);
#endif
  a = 1ULL << ((64 - d) / 3 + 1);

  for (; a * a * a > n;) {
    a = (2 * a + n / a / a) / 3;
  }
  return a;
}

/* HyStart++ constants */
#define NGTCP2_HS_MIN_SSTHRESH 16
#define NGTCP2_HS_N_RTT_SAMPLE 8
#define NGTCP2_HS_MIN_ETA (4 * NGTCP2_MILLISECONDS)
#define NGTCP2_HS_MAX_ETA (16 * NGTCP2_MILLISECONDS)

void ngtcp2_cc_scubic2_cc_on_pkt_acked(ngtcp2_cc *ccx, ngtcp2_conn_stat *cstat,
                                       const ngtcp2_cc_pkt *pkt,
                                       ngtcp2_tstamp ts) {
  ngtcp2_scubic2_cc *cc = ngtcp2_struct_of(ccx->ccb, ngtcp2_scubic2_cc, ccb);
  ngtcp2_duration t, min_rtt, eta;
  uint64_t target;
  uint64_t tx, kx, time_delta, delta;
  uint64_t add, tcp_add;
  uint64_t m;

#ifdef SCUBIC2_PRINT_ACK
  fprintf(stderr,
          "----- PKT ACKED; pkt_num=%" PRIu64 "; pktlen=%" PRIu64
          "; pktns_id=%d; sent_ts=%" PRIu64 "; tx_in_flight=%" PRIu64
          "; is_app_limited=%d -----\n",
          pkt->pkt_num, pkt->pktlen, pkt->pktns_id, pkt->sent_ts,
          pkt->tx_in_flight, pkt->is_app_limited);
#endif

  if (setup_phase == NGTCP2_SCUBIC2_SETUP_PHASE_INITIAL &&
      pkt->pktns_id == NGTCP2_PKTNS_ID_APPLICATION && pkt->pkt_num >= 1) {
    cstat->cwnd = cstat->bytes_in_flight;
    cstat->ssthresh = cstat->cwnd;
    cstat->pacing_rate = 1;
    setup_phase = NGTCP2_SCUBIC2_SETUP_PHASE_EST;
    fprintf(stderr,
            "----- SET ssthresh=cwnd=%" PRIu64 ", pacing_rate = 0 | ts=%" PRIu64
            " -----\n",
            cstat->cwnd, ts);
    fprintf(stderr, "------------ EXIT STATEFUL INITIAL ------------\n");
  }

  if (setup_phase == NGTCP2_SCUBIC2_SETUP_PHASE_INITIAL ||
      setup_phase == NGTCP2_SCUBIC2_SETUP_PHASE_EST) {
    return;
  }

  if (pkt->pktns_id == NGTCP2_PKTNS_ID_APPLICATION && cc->window_end != -1 &&
      cc->window_end <= pkt->pkt_num) {
    cc->window_end = -1;
  }

  if (in_congestion_recovery(cstat, pkt->sent_ts)) {
    return;
  }

  if (setup_phase == NGTCP2_SCUBIC2_SETUP_PHASE_DRAIN) {
    if (pkt->sent_ts >= DRAIN_start_ts) {
      cstat->cwnd = cstat->bytes_in_flight;
      cstat->ssthresh = cstat->cwnd;
      cstat->pacing_rate = 0;
      setup_phase = NGTCP2_SCUBIC2_SETUP_PHASE_END;
      fprintf(stderr,
              "----- SET ssthresh=cwnd=%" PRIu64
              ", pacing_rate = 0 | ts=%" PRIu64 " -----\n",
              cstat->cwnd, ts);
      fprintf(stderr, "-------------- EXIT DRAIN PHASE ---------------\n");
    } else {
      return;
    }
  }

  /* Has something wrong with Stateful-Cubic */
  // if (cc->target_cwnd && cc->target_cwnd < cstat->cwnd) {
  //   return;
  // }

  if (cstat->cwnd < cstat->ssthresh) {
    /* slow-start */
    cstat->cwnd += pkt->pktlen;

    ngtcp2_log_info(cc->ccb.log, NGTCP2_LOG_EVENT_RCV,
                    "pkn=%" PRId64 " acked, slow start cwnd=%" PRIu64,
                    pkt->pkt_num, cstat->cwnd);
#ifdef SCUBIC2_PRINT_CC_LOG
    fprintf(stderr, "pkn=%" PRId64 " acked, slow start cwnd=%" PRIu64 "\n",
            pkt->pkt_num, cstat->cwnd);
#endif

    if (cc->last_round_min_rtt != UINT64_MAX &&
        cc->current_round_min_rtt != UINT64_MAX &&
        cstat->cwnd >= NGTCP2_HS_MIN_SSTHRESH * cstat->max_udp_payload_size &&
        cc->rtt_sample_count >= NGTCP2_HS_N_RTT_SAMPLE) {
      eta = cc->last_round_min_rtt / 8;

      if (eta < NGTCP2_HS_MIN_ETA) {
        eta = NGTCP2_HS_MIN_ETA;
      } else if (eta > NGTCP2_HS_MAX_ETA) {
        eta = NGTCP2_HS_MAX_ETA;
      }

      if (cc->current_round_min_rtt >= cc->last_round_min_rtt + eta) {
        ngtcp2_log_info(cc->ccb.log, NGTCP2_LOG_EVENT_RCV,
                        "HyStart++ exit slow start");
        fprintf(stderr, "HyStart++ exit slow start\n");

        cc->w_last_max = cstat->cwnd;
        cstat->ssthresh = cstat->cwnd;
      }
    }
    return;
  }

  /* congestion avoidance */

  if (cc->epoch_start == UINT64_MAX) {
    cc->epoch_start = ts;
    if (cstat->cwnd < cc->w_last_max) {
      cc->k = ngtcp2_cbrt((cc->w_last_max - cstat->cwnd) * 10 / 4 /
                          cstat->max_udp_payload_size);
      cc->origin_point = cc->w_last_max;
    } else {
      cc->k = 0;
      cc->origin_point = cstat->cwnd;
    }

    cc->w_tcp = cstat->cwnd;

    ngtcp2_log_info(cc->ccb.log, NGTCP2_LOG_EVENT_RCV,
                    "scubic2-ca epoch_start=%" PRIu64 " k=%" PRIu64
                    " origin_point=%" PRIu64,
                    cc->epoch_start, cc->k, cc->origin_point);
#ifdef SCUBIC2_PRINT_CC_LOG
    fprintf(stderr,
            "scubic2-ca epoch_start=%" PRIu64 " k=%" PRIu64
            " origin_point=%" PRIu64 "\n",
            cc->epoch_start, cc->k, cc->origin_point);
#endif

    cc->pending_add = 0;
    cc->pending_w_add = 0;
  }

  min_rtt = cstat->min_rtt == UINT64_MAX ? cstat->initial_rtt : cstat->min_rtt;

  t = ts + min_rtt - cc->epoch_start;

  tx = (t << 4) / NGTCP2_SECONDS;
  kx = (cc->k << 4);

  if (tx > kx) {
    time_delta = tx - kx;
  } else {
    time_delta = kx - tx;
  }

  delta = cstat->max_udp_payload_size *
          ((((time_delta * time_delta) >> 4) * time_delta) >> 8) * 4 / 10;

  if (tx > kx) {
    target = cc->origin_point + delta;
  } else {
    target = cc->origin_point - delta;
  }

  if (target > cstat->cwnd) {
    m = cc->pending_add + cstat->max_udp_payload_size * (target - cstat->cwnd);
    add = m / cstat->cwnd;
    cc->pending_add = m % cstat->cwnd;
  } else {
    m = cc->pending_add + cstat->max_udp_payload_size;
    add = m / (100 * cstat->cwnd);
    cc->pending_add = m % (100 * cstat->cwnd);
  }

  m = cc->pending_w_add + cstat->max_udp_payload_size * pkt->pktlen;

  cc->w_tcp += m / cstat->cwnd;
  cc->pending_w_add = m % cstat->cwnd;

  if (cc->w_tcp > cstat->cwnd) {
    tcp_add =
        cstat->max_udp_payload_size * (cc->w_tcp - cstat->cwnd) / cstat->cwnd;
    if (tcp_add > add) {
      add = tcp_add;
    }
  }

  cstat->cwnd += add;

  ngtcp2_log_info(cc->ccb.log, NGTCP2_LOG_EVENT_RCV,
                  "pkn=%" PRId64 " acked, scubic2-ca cwnd=%" PRIu64
                  " t=%" PRIu64 " k=%" PRIi64 " time_delta=%" PRIu64
                  " delta=%" PRIu64 " target=%" PRIu64 " w_tcp=%" PRIu64,
                  pkt->pkt_num, cstat->cwnd, t, cc->k, time_delta >> 4, delta,
                  target, cc->w_tcp);
#ifdef SCUBIC2_PRINT_CC_LOG
  fprintf(stderr,
          "pkn=%" PRId64 " acked, scubic2-ca cwnd=%" PRIu64 " t=%" PRIu64
          " k=%" PRIi64 " time_delta=%" PRIu64 " delta=%" PRIu64
          " target=%" PRIu64 " w_tcp=%" PRIu64 "\n",
          pkt->pkt_num, cstat->cwnd, t, cc->k, time_delta >> 4, delta, target,
          cc->w_tcp);
#endif
}

void ngtcp2_cc_scubic2_cc_congestion_event(ngtcp2_cc *ccx,
                                           ngtcp2_conn_stat *cstat,
                                           ngtcp2_tstamp sent_ts,
                                           ngtcp2_tstamp ts) {
  ngtcp2_scubic2_cc *cc = ngtcp2_struct_of(ccx->ccb, ngtcp2_scubic2_cc, ccb);
  uint64_t min_cwnd;

  if (in_congestion_recovery(cstat, sent_ts)) {
    return;
  }

  if (setup_phase == NGTCP2_SCUBIC2_SETUP_PHASE_INITIAL) {
    fprintf(
        stderr,
        "packet loss but not reduce cwnd because of STATEFUL INITIAL phase\n");
    return;
  }

  if (DRAIN_start_ts != UINT64_MAX && sent_ts <= DRAIN_start_ts) {
    cstat->cwnd = cstat->bytes_in_flight;
    fprintf(stderr,
            "----- SET cwnd=%" PRIu64 " | pacing_rate = %lf, ts=%" PRIu64
            " -----\n",
            cstat->cwnd, cstat->pacing_rate, ts);
    fprintf(stderr, "packet loss in STATEFUL DRAIN phase\n");
    return;
  }

  if (setup_phase == NGTCP2_SCUBIC2_SETUP_PHASE_EST) {
    cstat->cwnd = cstat->bytes_in_flight;
    fprintf(stderr,
            "----- SET cwnd=%" PRIu64 " | pacing_rate = %lf, ts=%" PRIu64
            " -----\n",
            cstat->cwnd, cstat->pacing_rate, ts);
    fprintf(stderr, "packet loss in STATEFUL EST phase\n");
    return;
  }

  if (cc->prior.cwnd < cstat->cwnd) {
    cc->prior.cwnd = cstat->cwnd;
    cc->prior.ssthresh = cstat->ssthresh;
    cc->prior.w_last_max = cc->w_last_max;
    cc->prior.w_tcp = cc->w_tcp;
    cc->prior.origin_point = cc->origin_point;
    cc->prior.epoch_start = cc->epoch_start;
    cc->prior.k = cc->k;
  }

  cstat->congestion_recovery_start_ts = ts;

  cc->epoch_start = UINT64_MAX;
  if (cstat->cwnd < cc->w_last_max) {
    cc->w_last_max = cstat->cwnd * 17 / 10 / 2;
  } else {
    cc->w_last_max = cstat->cwnd;
  }

  min_cwnd = 2 * cstat->max_udp_payload_size;
  cstat->ssthresh = cstat->cwnd * 7 / 10;
  cstat->ssthresh = ngtcp2_max(cstat->ssthresh, min_cwnd);
  cstat->cwnd = cstat->ssthresh;

  ngtcp2_log_info(cc->ccb.log, NGTCP2_LOG_EVENT_RCV,
                  "reduce cwnd because of packet loss cwnd=%" PRIu64,
                  cstat->cwnd);
  fprintf(stderr, "reduce cwnd because of packet loss cwnd=%" PRIu64 "\n",
          cstat->cwnd);
}

void ngtcp2_cc_scubic2_cc_on_spurious_congestion(ngtcp2_cc *ccx,
                                                 ngtcp2_conn_stat *cstat,
                                                 ngtcp2_tstamp ts) {
  ngtcp2_scubic2_cc *cc = ngtcp2_struct_of(ccx->ccb, ngtcp2_scubic2_cc, ccb);
  (void)ts;

  if (cstat->cwnd >= cc->prior.cwnd) {
    return;
  }

  cstat->congestion_recovery_start_ts = UINT64_MAX;

  cstat->cwnd = cc->prior.cwnd;
  cstat->ssthresh = cc->prior.ssthresh;
  cc->w_last_max = cc->prior.w_last_max;
  cc->w_tcp = cc->prior.w_tcp;
  cc->origin_point = cc->prior.origin_point;
  cc->epoch_start = cc->prior.epoch_start;
  cc->k = cc->prior.k;

  cc->prior.cwnd = 0;
  cc->prior.ssthresh = 0;
  cc->prior.w_last_max = 0;
  cc->prior.w_tcp = 0;
  cc->prior.origin_point = 0;
  cc->prior.epoch_start = UINT64_MAX;
  cc->prior.k = 0;

  ngtcp2_log_info(cc->ccb.log, NGTCP2_LOG_EVENT_RCV,
                  "spurious congestion is detected and congestion state is "
                  "restored cwnd=%" PRIu64,
                  cstat->cwnd);
  fprintf(stderr,
          "spurious congestion is detected and congestion state is "
          "restored cwnd=%" PRIu64 "\n",
          cstat->cwnd);
}

void ngtcp2_cc_scubic2_cc_on_persistent_congestion(ngtcp2_cc *ccx,
                                                   ngtcp2_conn_stat *cstat,
                                                   ngtcp2_tstamp ts) {
  (void)ccx;
  (void)ts;

  cstat->cwnd = 2 * cstat->max_udp_payload_size;
  cstat->congestion_recovery_start_ts = UINT64_MAX;
  fprintf(stderr, "persistent congestion cwnd=%" PRIu64 "\n", cstat->cwnd);
}

void ngtcp2_cc_scubic2_cc_on_ack_recv(ngtcp2_cc *ccx, ngtcp2_conn_stat *cstat,
                                      const ngtcp2_cc_ack *ack,
                                      ngtcp2_tstamp ts) {
  ngtcp2_scubic2_cc *cc = ngtcp2_struct_of(ccx->ccb, ngtcp2_scubic2_cc, ccb);
  uint64_t target_cwnd, initcwnd;
  (void)ack;
  (void)ts;

#ifdef SCUBIC2_PRINT_ACK
  fprintf(stderr,
          "----- ACK RECV; prior_bytes_in_flight=%" PRIu64
          "; bytes_delivered=%" PRIu64 "; now_ts=%" PRIu64 " -----\n",
          ack->prior_bytes_in_flight, ack->bytes_delivered, ts);
#endif
  if (setup_phase == NGTCP2_SCUBIC2_SETUP_PHASE_EST &&
      rtt_sample_idx < RTT_SAMPLE_SIZE) {
    rtt_samples[rtt_sample_idx].sent_ts = ack->largest_acked_sent_ts;
    rtt_samples[rtt_sample_idx].recv_ts = ts;
    rtt_samples[rtt_sample_idx].rtt = ack->rtt;
    rtt_samples[rtt_sample_idx].bytes_delivered = ack->bytes_delivered;
    rtt_sample_idx++;
    if (rtt_sample_idx == RTT_SAMPLE_SIZE) {
      uint64_t bytes_delivere_sum = 0;
      uint64_t start_ts = rtt_samples[0].recv_ts;
      uint64_t btl_bw_estimated = 0;
      uint64_t cwnd_preferred = 0;
#ifdef SCUBIC2_PRINT_RTT
      fprintf(stderr, "-----  PRINT RTT SAMPLES  -----\n");
      fprintf(stderr,
              "rtt_samples[0].sent_ts=%" PRIu64
              "; rtt_samples[0].recv_ts=%" PRIu64 "; recv_ts - sent_ts=%" PRIu64
              "; rtt_samples[0].rtt=%" PRIu64
              "; rtt_samples[0].bytes_delivered=%" PRIu64 "\n",
              rtt_samples[0].sent_ts, rtt_samples[0].recv_ts,
              rtt_samples[0].recv_ts - rtt_samples[0].sent_ts,
              rtt_samples[0].rtt, rtt_samples[0].bytes_delivered);
#endif
      for (size_t i = 1; i < RTT_SAMPLE_SIZE; i++) {
        bytes_delivere_sum += rtt_samples[i].bytes_delivered;
        if (rtt_samples[i].recv_ts == start_ts) {
          btl_bw_estimated = UINT64_MAX;
          cwnd_preferred = UINT64_MAX;
        } else {
          btl_bw_estimated = bytes_delivere_sum * NGTCP2_SECONDS /
                             (rtt_samples[i].recv_ts - start_ts);
          cwnd_preferred = btl_bw_estimated * cstat->min_rtt / NGTCP2_SECONDS;
        }
#ifdef SCUBIC2_PRINT_RTT
        fprintf(stderr,
                "rtt_samples[%zu].sent_ts=%" PRIu64
                "; rtt_samples[%zu].recv_ts=%" PRIu64
                "; recv_ts - sent_ts=%" PRIu64 "; rtt_samples[%zu].rtt=%" PRIu64
                "; rtt_samples[%zu].bytes_delivered=%" PRIu64
                "; btl_bw_estimated=%" PRIu64 "\n",
                i, rtt_samples[i].sent_ts, i, rtt_samples[i].recv_ts,
                rtt_samples[i].recv_ts - rtt_samples[i].sent_ts, i,
                rtt_samples[i].rtt, i, rtt_samples[i].bytes_delivered,
                btl_bw_estimated);
#endif
        fprintf(stderr,
                "-- btl_bw_estimated=%" PRIu64 "; min_rtt=%" PRIu64
                "; cwnd_preferred=%" PRIu64 "; now_cwnd=%" PRIu64 "  --\n",
                btl_bw_estimated, cstat->min_rtt, cwnd_preferred, cstat->cwnd);
      }
      fprintf(stderr, "----- RTT SAMPLES PRINTED -----\n");

      fprintf(stderr, "-------------- EXIT STATEFUL EST --------------\n");
      // if (cwnd_preferred < cstat->cwnd * 8 / 10) {
      if (cwnd_preferred * 2 < cstat->cwnd) {
        fprintf(stderr, "----------------- DRAIN PHASE -----------------\n");
        setup_phase = NGTCP2_SCUBIC2_SETUP_PHASE_DRAIN;
        DRAIN_start_ts = ts;
        cstat->pacing_rate = (double)btl_bw_estimated / NGTCP2_SECONDS;
        cstat->cwnd += 2 * btl_bw_estimated * cstat->min_rtt / NGTCP2_SECONDS;
        cstat->send_quantum = ngtcp2_max(
            cstat->max_udp_payload_size,
            (size_t)(5.0 * cstat->pacing_rate * NGTCP2_MILLISECONDS));
        fprintf(stderr, "----- ESTIMATE send_quantum=%" PRIu64 " -----\n",
                (size_t)(5.0 * cstat->pacing_rate * NGTCP2_MILLISECONDS));
        fprintf(stderr,
                "----- SET cwnd=%" PRIu64 ", send_quantum=%" PRIu64
                ", pacing_rate = %lf | ts=%" PRIu64 " -----\n",
                cstat->cwnd, cstat->send_quantum, cstat->pacing_rate, ts);
      } else {
        fprintf(stderr, "----------------- PROBE PHASE -----------------\n");
        setup_phase = NGTCP2_SCUBIC2_SETUP_PHASE_PROBE;
        DRAIN_start_ts = UINT64_MAX;
        cstat->ssthresh = UINT64_MAX;
      }
    }
  }

  if (current_state != NULL) {
    current_state->btl_bw =
        smooth_btl_bw_on_ack_recv(ts, ack->bytes_delivered, cstat);
#ifdef SCUBIC2_PRINT_CC_LOG
    fprintf(stderr,
            "----- CHANGE btl_bw=%" PRIu64 "; NOW smoothed_rtt=%" PRIu64
            " -----\n",
            current_state->btl_bw, cstat->smoothed_rtt);
#endif
  }

  /* TODO Use sliding window for min rtt measurement */
  /* TODO Use sliding window */
  cc->max_delivery_rate_sec =
      ngtcp2_max(cc->max_delivery_rate_sec, cstat->delivery_rate_sec);

  if (cstat->min_rtt != UINT64_MAX && cc->max_delivery_rate_sec) {
    target_cwnd = cc->max_delivery_rate_sec * cstat->min_rtt / NGTCP2_SECONDS;
    initcwnd = ngtcp2_cc_compute_initcwnd(cstat->max_udp_payload_size);
    cc->target_cwnd = ngtcp2_max(initcwnd, target_cwnd) * 289 / 100;

    ngtcp2_log_info(cc->ccb.log, NGTCP2_LOG_EVENT_RCV,
                    "target_cwnd=%" PRIu64 " max_delivery_rate_sec=%" PRIu64
                    " min_rtt=%" PRIu64,
                    cc->target_cwnd, cc->max_delivery_rate_sec, cstat->min_rtt);
#ifdef SCUBIC2_PRINT_CC_LOG
    fprintf(stderr,
            "target_cwnd=%" PRIu64 " max_delivery_rate_sec=%" PRIu64
            " min_rtt=%" PRIu64 "\n",
            cc->target_cwnd, cc->max_delivery_rate_sec, cstat->min_rtt);
#endif
  }
}

void ngtcp2_cc_scubic2_cc_on_pkt_sent(ngtcp2_cc *ccx, ngtcp2_conn_stat *cstat,
                                      const ngtcp2_cc_pkt *pkt) {
  ngtcp2_scubic2_cc *cc = ngtcp2_struct_of(ccx->ccb, ngtcp2_scubic2_cc, ccb);
#ifdef SCUBIC2_PRINT_SENT
  fprintf(stderr, "---- pkt_sent pkn=%" PRId64 "\n", pkt->pkt_num);
  fprintf(stderr, "-- sent_ts=%" PRId64 "\n", pkt->sent_ts);
  fprintf(stderr, "-- cwnd=%" PRId64 "; bytes_in_flight=%" PRId64 "\n",
          cstat->cwnd, cstat->bytes_in_flight);
  fprintf(stderr, "-- delivery_rate_sec=%" PRIu64 "\n",
          cstat->delivery_rate_sec);
  fprintf(stderr, "-- send_quantum=%" PRIu64 "\n", cstat->send_quantum);
#endif
  (void)cstat;

  if (pkt->pktns_id != NGTCP2_PKTNS_ID_APPLICATION || cc->window_end != -1) {
    return;
  }

  cc->window_end = pkt->pkt_num;
  cc->last_round_min_rtt = cc->current_round_min_rtt;
  cc->current_round_min_rtt = UINT64_MAX;
  cc->rtt_sample_count = 0;
}

void ngtcp2_cc_scubic2_cc_new_rtt_sample(ngtcp2_cc *ccx,
                                         ngtcp2_conn_stat *cstat,
                                         ngtcp2_tstamp ts) {
  ngtcp2_scubic2_cc *cc = ngtcp2_struct_of(ccx->ccb, ngtcp2_scubic2_cc, ccb);
  (void)ts;

  if (cc->window_end == -1) {
    return;
  }

  cc->current_round_min_rtt =
      ngtcp2_min(cc->current_round_min_rtt, cstat->latest_rtt);
  ++cc->rtt_sample_count;

  if (current_state != NULL) {
    current_state->min_rtt = cstat->min_rtt;
#ifdef SCUBIC2_PRINT_CC_LOG
    fprintf(stderr,
            "----- CHANGE min_rtt=%" PRIu64 "; now_ts=%" PRIu64 " -----\n",
            current_state->min_rtt, ts);
#endif
  }
}

void ngtcp2_cc_scubic2_cc_reset(ngtcp2_cc *ccx, ngtcp2_conn_stat *cstat,
                                ngtcp2_tstamp ts) {
  ngtcp2_scubic2_cc *cc = ngtcp2_struct_of(ccx->ccb, ngtcp2_scubic2_cc, ccb);
  (void)cstat;
  (void)ts;

  scubic2_cc_reset(cc);
}

void ngtcp2_cc_scubic2_cc_event(ngtcp2_cc *ccx, ngtcp2_conn_stat *cstat,
                                ngtcp2_cc_event_type event, ngtcp2_tstamp ts) {
  ngtcp2_scubic2_cc *cc = ngtcp2_struct_of(ccx->ccb, ngtcp2_scubic2_cc, ccb);
  ngtcp2_tstamp last_ts;

  if (event != NGTCP2_CC_EVENT_TYPE_TX_START || cc->epoch_start == UINT64_MAX) {
    return;
  }

  last_ts = cstat->last_tx_pkt_ts[NGTCP2_PKTNS_ID_APPLICATION];
  if (last_ts == UINT64_MAX || last_ts <= cc->epoch_start) {
    return;
  }

  assert(ts >= last_ts);

  cc->epoch_start += ts - last_ts;
}
