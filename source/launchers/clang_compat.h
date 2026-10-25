/* SPDX-License-Identifier: GPL-2.0-or-later
 * The public FidelityFX source expects MSVC's array-count helper on Windows.
 * CLANG64 needs the equivalent compile-time expression; no runtime change.
 */
#pragma once
#ifndef _countof
#define _countof(array) (sizeof(array) / sizeof((array)[0]))
#endif
