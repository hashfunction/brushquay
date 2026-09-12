# Original notice catalog integration

This data-only candidate supplies original copyright/license material for the selected Bristlune dependency inventory. It does not change product code, runtime selection, installation, GUI acceptance, package export or workflows.

`original-notices/catalog.json` records 1,292 original/context files, 11,745,137 bytes, under 90 component owners. The original 918-file collection (6,445,405 bytes) is retained unchanged. Supplements include 116 exact DrMinGW notice blocks (114,929 bytes), original source/build context, complete XZ Windows runtime notices, exact Python Windows build conditions, Microsoft Runtime/Community documents and original SDK18362 license/REDIST records. No executable DLL, installer or source archive is added.

The catalog distinguishes 68 selected runtime owners, 11 build tools and 11 owners with no separately selected runtime file whose header/static use is not inferred from that absence. Its 121 associations distinguish selected, conditional, separate-owner, tool-only, non-selected and unresolved source bindings. The original identifiedSourceGrants entries are file/subcomponent evidence and may cover build scripts or examples. They are not principal runtime expressions. Thirteen owners now have separate manually scoped primaryRuntimeGrants with original source/header evidence, exact selected-file associations and an index that presents these primary terms first. Full-license templates and subsidiary terms remain separately labeled; neither list asserts aggregate compatibility.

Specific findings preserved:

- Win-iconv0.0.8 explicitly places win_iconv.c in the public domain. It is not GNU libiconv.
- DrMinGW includes LGPL2.1, SGI and BSD libdwarf notices, zlib, permissive Fonseca headers, and the original GPL/Library-GPL demangler compiled-link exceptions.
- XZ's full COPYING-Windows.txt is required by the original binary README and retained without pruning sections.
- System FreeType does not remove Qt Gui's gray-raster attribution. ICU does not remove the TSCII codec notice. Optional Qt feature notices are retained without guessing configuration outcomes.
- PyQt6's original PKG-INFO states GPL-3.0-only. Qt Core's original SPDX declaration remains distinct from the Qt third-party attribution records.
- Microsoft's Python build conditions, Runtime end-user terms, downstream distributor reference and SDK18362 terms retain their separate roles and apply only to Microsoft Distributable Code.

The libvpx1.13.1 upstream notice is explicitly reference-qualified while the producer meson-2 revision remains unresolved. OpenSSL1.1.1/Qt/GPL compatibility is undergoing a separate source-backed review. Neither question is silently converted into a licensing approval flag.

The source-input release URL is recorded for navigation. Final anonymous source-publication binding, final selected-package applicability and package/Store license presentation remain separate release work.

Verification:

```sh
python3 distribution/native-source/test_original_notices.py -v
```

All nine focused tests pass: full catalog byte/reference/excerpt integrity; original918 and116-block counts/bytes; wrong byte count/hash refusal; unsafe/duplicate-path refusal; scoped Qt/Microsoft/source-grant selection checks; 13 primary-owner expression/proof/index checks; foreign selected-file/source-proof refusal; exact six-DLL FFmpeg receipt/export instruction/configuration cross-binding; and a real Git checkout with core.autocrlf=true preserving representative original TXT, CRLF text, DOCX, RTF and C++ bytes. `.gitattributes` preserves original catalog bytes on Windows. No source-archive-set hash pass, native build or broad suite was run.


## Primary grant supplement

| Selected owner | Primary grant and specific scope |
| --- | --- |
| LAME | LGPL-2.0-or-later from the public library header; MIT belongs to the build overlay. |
| libde265 | LGPL-3.0-or-later from the decoder API; MIT samples remain separate. |
| x265 | GPL-2.0-or-later from x265.h; commercial licensing is an alternative offer, not an asserted entitlement. MIT HDR/json11 notices remain separate. |
| OpenSSL 1.1.1l | The original OpenSSL and original SSLeay conditions both apply; BSD Text-Template is subsidiary. Qt/GPL combination review remains separate. |
| libpng 1.6.51 | libpng-2.0; complete original historical version-1 notices also retained. |
| SDL2 and zlib | Zlib principal grants; HIDAPI BSD and DotZLib BSL files do not replace them. |
| LLVM runtimes | Apache-2.0 WITH LLVM-exception for libc++, libomp and libunwind; winpthreads is MIT AND BSD-3-Clause. Original MinGW and subsidiary runtime notices remain. |
| CPython | Principal PSF-2.0, with full original historical BeOpen/CNRI/CWI notices; separate extension and Microsoft terms remain. |
| libjpeg-turbo | IJG AND BSD-3-Clause AND Zlib, mapped in its own LICENSE.md to inherited libjpeg, TurboJPEG and SIMD code; original README.ijg and SIMD source are now included. |
| Gettext | Selected intl.dll is LGPL-2.1-or-later. libasprintf source is also LGPL but no separate DLL is selected. GPL tool source and selected locale resources are not relabeled by the intl grant. |
| ICU 72 | Unicode-DFS-2016 AND ICU principal grants, with all original additional dictionary/data notices preserved; build-overlay MIT remains separate. |
| FFmpeg | Actual selected DLL license-return functions establish LGPL-2.1-or-later, agreeing with the exact Meson recipe. |

FFmpeg is built with Meson. The retained exact source defaults disable `gpl`, `version3` and `nonfree`; the recipe, shared initialization and compiler/host templates do not override them. All 13 applied patches are retained (number 0004 is absent; two files under skipped_patches are not applied). The recipe hash equals its original locked binary-input recipe record.

The original dependency archive is 149,012,480 bytes, SHA256 `1b275992dace0c159c72bc0ca9772d6a83d3b5c0a6b64dab6595092ec2381cdd`. Independently reproduced read-only checks of all six contained DLLs matched their selected inventory hashes and all twelve named `av*_license`/`sw*_license` and configuration exports. Each exact eight-byte function body is `lea rax,[rip+signed_disp32]; ret`; its derived address resolves to the recorded original string. All six license strings are `LGPL version 2.1 or later`, and the six configuration strings agree without GPL/version3/nonfree overrides. The source-owned JSON receipt includes the export RVAs, file offsets, instruction bytes and strings; no DLL is executed or added to source.

This supplement adds 33 exact original/context/observation files totaling 931,540 bytes. Verification was targeted: the nine tests pass in under one second, and the six original DLL observations were independently replayed once. The original 918 notices and 116 DrMinGW blocks are unchanged. No full archive-set hash pass, build, runtime selection or pipeline edit was performed.
