/**
 * Path data for the sample signature the signature pad replays in its demo.
 *
 * The original lab shipped a drawn signature as raw path data, which did not
 * travel with the component set. This is a hand-authored cursive mark standing
 * in for it: the same shape of data, but not the original artwork. Replace
 * `SIGNATURE` with the real path if you have it — nothing else needs to change,
 * as long as the coordinates stay inside `SIGNATURE_VIEWBOX`.
 */

/** Cursive sample signature, multiple subpaths separated by `M`. */
export const SIGNATURE =
  "M8 78 C22 44 30 22 38 22 C45 22 44 40 40 56 C37 68 40 76 48 72 C58 66 62 40 70 34 C76 30 80 40 76 52 C73 62 76 70 84 68 C96 65 104 44 112 40 C118 37 122 46 118 58 C115 68 118 74 126 71 C138 66 146 48 156 42 C162 38 168 46 165 58 C162 70 166 76 176 73 C190 69 200 52 212 46 C218 43 224 50 221 62 C218 74 224 79 236 75 C248 71 258 58 268 52 C274 48 280 55 277 66 C274 78 280 82 292 78 C304 74 314 64 322 58"

/** `minX minY width height`, matching the coordinate space SIGNATURE is drawn in. */
export const SIGNATURE_VIEWBOX = "0 0 340 100"
