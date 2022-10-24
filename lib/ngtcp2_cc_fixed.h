#ifndef NGTCP2_CC_FIXED_H
#define NGTCP2_CC_FIXED_H

#ifdef HAVE_CONFIG_H
#  include <config.h>
#endif /* HAVE_CONFIG_H */

#include <ngtcp2/ngtcp2.h>

#include "ngtcp2_cc.h"

/* ngtcp2_fixed_cc is the FIXED congestion controller. */
typedef struct ngtcp2_fixed_cc {
  ngtcp2_cc_base ccb;
} ngtcp2_fixed_cc;

int ngtcp2_cc_fixed_cc_init(ngtcp2_cc *cc, ngtcp2_log *log,
                            ngtcp2_conn_stat *cstat, const ngtcp2_mem *mem,
                            const ngtcp2_path *path);

void ngtcp2_cc_fixed_cc_free(ngtcp2_cc *cc, const ngtcp2_mem *mem);

void ngtcp2_fixed_cc_init(ngtcp2_fixed_cc *cc, ngtcp2_log *log);

void ngtcp2_fixed_cc_free(ngtcp2_fixed_cc *cc);

void ngtcp2_cc_fixed_cc_on_pkt_acked(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                     const ngtcp2_cc_pkt *pkt,
                                     ngtcp2_tstamp ts);

void ngtcp2_cc_fixed_cc_congestion_event(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                         ngtcp2_tstamp sent_ts,
                                         ngtcp2_tstamp ts);

void ngtcp2_cc_fixed_cc_on_persistent_congestion(ngtcp2_cc *cc,
                                                 ngtcp2_conn_stat *cstat,
                                                 ngtcp2_tstamp ts);

void ngtcp2_cc_fixed_cc_on_ack_recv(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                                    const ngtcp2_cc_ack *ack, ngtcp2_tstamp ts);

void ngtcp2_cc_fixed_cc_reset(ngtcp2_cc *cc, ngtcp2_conn_stat *cstat,
                              ngtcp2_tstamp ts);

#endif /* NGTCP2_CC_FIXED_H */
