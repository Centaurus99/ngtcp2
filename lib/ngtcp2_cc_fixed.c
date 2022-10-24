
#include "ngtcp2_cc_fixed.h"

#include <stdio.h>

#if defined(_MSC_VER)
#  include <intrin.h>
#endif

#include "ngtcp2_log.h"
#include "ngtcp2_macro.h"
#include "ngtcp2_mem.h"
#include "ngtcp2_rcvry.h"

static void fixed_cc_reset(ngtcp2_fixed_cc *cc) { (void)cc; }

void ngtcp2_fixed_cc_init(ngtcp2_fixed_cc *cc, ngtcp2_log *log) {
  cc->ccb.log = log;
  fixed_cc_reset(cc);
}

void ngtcp2_fixed_cc_free(ngtcp2_fixed_cc *cc) { (void)cc; }

int ngtcp2_cc_fixed_cc_init(ngtcp2_cc *cc, ngtcp2_log *log,
                            ngtcp2_conn_stat *cstat, const ngtcp2_mem *mem,
                            const ngtcp2_path *path) {
  ngtcp2_fixed_cc *fixed_cc;
  uint64_t btl_bw = 3000000 * 1.0;
  uint64_t min_rtt = 40000000;

  (void)path;

  fixed_cc = ngtcp2_mem_calloc(mem, 1, sizeof(ngtcp2_fixed_cc));
  if (fixed_cc == NULL) {
    return NGTCP2_ERR_NOMEM;
  }

  ngtcp2_fixed_cc_init(fixed_cc, log);

  cc->ccb = &fixed_cc->ccb;
  cc->on_pkt_acked = ngtcp2_cc_fixed_cc_on_pkt_acked;
  cc->congestion_event = ngtcp2_cc_fixed_cc_congestion_event;
  cc->on_persistent_congestion = ngtcp2_cc_fixed_cc_on_persistent_congestion;
  cc->on_ack_recv = ngtcp2_cc_fixed_cc_on_ack_recv;
  cc->reset = ngtcp2_cc_fixed_cc_reset;

  fprintf(stderr, "-------------------- START --------------------\n");

  cstat->pacing_rate = 1.5 * (double)btl_bw / NGTCP2_SECONDS;
  cstat->cwnd = btl_bw * min_rtt * 3 / 2 / NGTCP2_SECONDS;

  fprintf(stderr, "----- SET cwnd=%" PRIu64 " -----\n", cstat->cwnd);
  fprintf(stderr, "----- SET pacing_rate=%lf -----\n", cstat->pacing_rate);

  return 0;
}

void ngtcp2_cc_fixed_cc_free(ngtcp2_cc *cc, const ngtcp2_mem *mem) {
  ngtcp2_fixed_cc *fixed_cc = ngtcp2_struct_of(cc->ccb, ngtcp2_fixed_cc, ccb);

  ngtcp2_fixed_cc_free(fixed_cc);
  ngtcp2_mem_free(mem, fixed_cc);
}

void ngtcp2_cc_fixed_cc_on_pkt_acked(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                     const ngtcp2_cc_pkt *pkt,
                                     ngtcp2_tstamp ts) {
  (void)cc;
  (void)cstat;
  (void)pkt;
  (void)ts;
}

void ngtcp2_cc_fixed_cc_congestion_event(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                         ngtcp2_tstamp sent_ts,
                                         ngtcp2_tstamp ts) {
  (void)cc;
  (void)cstat;
  (void)sent_ts;
  (void)ts;
}

void ngtcp2_cc_fixed_cc_on_persistent_congestion(ngtcp2_cc *cc,
                                                 ngtcp2_conn_stat *cstat,
                                                 ngtcp2_tstamp ts) {
  (void)cc;
  (void)cstat;
  (void)ts;
}

void ngtcp2_cc_fixed_cc_on_ack_recv(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                    const ngtcp2_cc_ack *ack,
                                    ngtcp2_tstamp ts) {
  (void)cc;
  (void)cstat;
  (void)ack;
  (void)ts;
}

void ngtcp2_cc_fixed_cc_reset(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                              ngtcp2_tstamp ts) {
  (void)cc;
  (void)cstat;
  (void)ts;
}