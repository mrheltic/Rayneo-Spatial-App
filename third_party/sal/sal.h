#pragma once

// Minimal SAL stub for non-Windows builds of DirectXMath.
//
// DirectXMath.h includes "sal.h" unconditionally; on Windows it comes from the
// SDK. Off Windows, DirectXMath's README asks for one on the include path.
// SAL annotations are static-analysis hints only, so every macro DirectXMath
// uses expands to nothing. If a newer DirectXMath pin uses another annotation,
// the build fails on an unknown identifier: add it here.

#ifndef _WIN32

#define _In_
#define _In_opt_
#define _In_reads_(size)
#define _In_reads_bytes_(size)
#define _Out_
#define _Out_opt_
#define _Out_writes_(size)
#define _Out_writes_bytes_(size)
#define _Inout_
#define _Success_(expr)
#define _Use_decl_annotations_
#define _Analysis_assume_(expr)

#endif
