#ifndef NGTCP2_STATEFUL_CUBIC_H
#define NGTCP2_STATEFUL_CUBIC_H

#ifdef HAVE_CONFIG_H
#  include <config.h>
#endif /* HAVE_CONFIG_H */

#include <ngtcp2/ngtcp2.h>

#include "ngtcp2_cc.h"

/* ngtcp2_scubic_cc is Stateful CUBIC congestion controller. */
typedef struct ngtcp2_scubic_cc {
  ngtcp2_cc_base ccb;
  uint64_t max_delivery_rate_sec;
  uint64_t target_cwnd;
  uint64_t w_last_max;
  uint64_t w_tcp;
  uint64_t origin_point;
  ngtcp2_tstamp epoch_start;
  uint64_t k;
  /* prior stores the congestion state when a congestion event occurs
     in order to restore the state when it turns out that the event is
     spurious. */
  struct {
    uint64_t cwnd;
    uint64_t ssthresh;
    uint64_t w_last_max;
    uint64_t w_tcp;
    uint64_t origin_point;
    ngtcp2_tstamp epoch_start;
    uint64_t k;
  } prior;
  /* HyStart++ variables */
  size_t rtt_sample_count;
  uint64_t current_round_min_rtt;
  uint64_t last_round_min_rtt;
  int64_t window_end;
  uint64_t pending_add;
  uint64_t pending_w_add;
} ngtcp2_scubic_cc;

typedef struct ngtcp2_scubic_state {
  struct in_addr address;
  uint64_t btl_bw;
  uint64_t min_rtt;
} ngtcp2_scubic_state;

int ngtcp2_cc_scubic_cc_init(ngtcp2_cc *cc, ngtcp2_log *log,
                             ngtcp2_conn_stat *cstat, const ngtcp2_mem *mem,
                             const ngtcp2_path *path);

void ngtcp2_cc_scubic_cc_free(ngtcp2_cc *cc, const ngtcp2_mem *mem);

void ngtcp2_scubic_cc_init(ngtcp2_scubic_cc *cc, ngtcp2_log *log);

void ngtcp2_scubic_cc_free(ngtcp2_scubic_cc *cc);

void ngtcp2_cc_scubic_cc_on_pkt_acked(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                      const ngtcp2_cc_pkt *pkt,
                                      ngtcp2_tstamp ts);

void ngtcp2_cc_scubic_cc_congestion_event(ngtcp2_cc *cc,
                                          ngtcp2_conn_stat *cstat,
                                          ngtcp2_tstamp sent_ts,
                                          ngtcp2_tstamp ts);

void ngtcp2_cc_scubic_cc_on_spurious_congestion(ngtcp2_cc *ccx,
                                                ngtcp2_conn_stat *cstat,
                                                ngtcp2_tstamp ts);

void ngtcp2_cc_scubic_cc_on_persistent_congestion(ngtcp2_cc *cc,
                                                  ngtcp2_conn_stat *cstat,
                                                  ngtcp2_tstamp ts);

void ngtcp2_cc_scubic_cc_on_ack_recv(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                     const ngtcp2_cc_ack *ack,
                                     ngtcp2_tstamp ts);

void ngtcp2_cc_scubic_cc_on_pkt_sent(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                     const ngtcp2_cc_pkt *pkt);

void ngtcp2_cc_scubic_cc_new_rtt_sample(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                        ngtcp2_tstamp ts);

void ngtcp2_cc_scubic_cc_reset(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                               ngtcp2_tstamp ts);

void ngtcp2_cc_scubic_cc_event(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                               ngtcp2_cc_event_type event, ngtcp2_tstamp ts);

#endif /* NGTCP2_STATEFUL_CC_H */
