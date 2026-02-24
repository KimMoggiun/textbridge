/*
 * Copyright (c) 2024 TextBridge Contributors
 *
 * SPDX-License-Identifier: MIT
 */

#pragma once

#include <zephyr/types.h>
#include <errno.h>

#ifdef CONFIG_ZMK_TEXTBRIDGE
int zmk_textbridge_pair_start(void);
void zmk_textbridge_get_status(uint8_t *advertising, uint8_t *connected, uint8_t *bonded);
#else
static inline int zmk_textbridge_pair_start(void) { return -ENOTSUP; }
static inline void zmk_textbridge_get_status(uint8_t *advertising, uint8_t *connected, uint8_t *bonded) {
    *advertising = 0; *connected = 0; *bonded = 0;
}
#endif
