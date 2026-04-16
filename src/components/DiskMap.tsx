import { BlockState, DiskBlock } from '@/lib/fileSystem';
import { motion } from 'framer-motion';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';

const ZOOM_MIN = 0.4;
const ZOOM_MAX = 6;

interface DiskMapProps {
  disk: DiskBlock[];
  highlightFile?: string | null;
}

interface ExtendedDiskBlock extends DiskBlock {
  allocStrategy?: string;
}

const stateColors: Record<string, string> = {
  free: 'bg-secondary',
  used: 'bg-primary/70',
  corrupted: 'bg-danger',
  reserved: 'bg-warning/60',
  journal: 'bg-info/60',
};

const stateSvgFills: Record<BlockState, string> = {
  free: 'hsl(var(--secondary))',
  used: 'hsl(var(--primary) / 0.7)',
  corrupted: 'hsl(var(--danger))',
  reserved: 'hsl(var(--warning) / 0.6)',
  journal: 'hsl(var(--info) / 0.6)',
};

/** Annulus sector: track = ring index (0 = innermost data ring), sector = angular slice. */
function wedgePath(
  cx: number,
  cy: number,
  rInner: number,
  rOuter: number,
  a0: number,
  a1: number,
): string {
  const x1 = cx + rOuter * Math.cos(a0);
  const y1 = cy + rOuter * Math.sin(a0);
  const x2 = cx + rOuter * Math.cos(a1);
  const y2 = cy + rOuter * Math.sin(a1);
  const x3 = cx + rInner * Math.cos(a1);
  const y3 = cy + rInner * Math.sin(a1);
  const x4 = cx + rInner * Math.cos(a0);
  const y4 = cy + rInner * Math.sin(a0);
  const large = a1 - a0 > Math.PI ? 1 : 0;
  return `M ${x1} ${y1} A ${rOuter} ${rOuter} 0 ${large} 1 ${x2} ${y2} L ${x3} ${y3} A ${rInner} ${rInner} 0 ${large} 0 ${x4} ${y4} Z`;
}

/** Split block count into rings × wedges (tracks × sectors) for a platter-style grid. */
function getPolarDims(n: number): { tracks: number; sectors: number } {
  if (n <= 1) return { tracks: 1, sectors: 1 };
  const root = Math.floor(Math.sqrt(n));
  for (let d = root; d >= 1; d--) {
    if (n % d === 0) {
      const a = d;
      const b = n / d;
      return a <= b ? { tracks: a, sectors: b } : { tracks: b, sectors: a };
    }
  }
  return { tracks: 1, sectors: n };
}

export default function DiskMap({ disk, highlightFile }: DiskMapProps) {
  const [hoveredFileId, setHoveredFileId] = useState<string | null>(null);
  const [circularLayout, setCircularLayout] = useState(false);
  const [diskZoom, setDiskZoom] = useState(1);
  const [diskPan, setDiskPan] = useState({ x: 0, y: 0 });
  const diskViewportRef = useRef<HTMLDivElement>(null);
  const diskPanRef = useRef(diskPan);
  diskPanRef.current = diskPan;
  const diskDragRef = useRef<{ active: boolean; px: number; py: number; ox: number; oy: number }>({
    active: false,
    px: 0,
    py: 0,
    ox: 0,
    oy: 0,
  });

  const resetDiskView = useCallback(() => {
    setDiskZoom(1);
    setDiskPan({ x: 0, y: 0 });
  }, []);

  const applyDiskWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const el = diskViewportRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const halfW = rect.width / 2;
    const halfH = rect.height / 2;
    const mx = e.clientX - rect.left - halfW;
    const my = e.clientY - rect.top - halfH;

    setDiskZoom((prevScale) => {
      const factor = e.deltaY < 0 ? 1.08 : 1 / 1.08;
      const nextScale = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, prevScale * factor));
      if (nextScale === prevScale) return prevScale;
      const ratio = nextScale / prevScale;
      const p = diskPanRef.current;
      setDiskPan({
        x: mx - ratio * (mx - p.x),
        y: my - ratio * (my - p.y),
      });
      return nextScale;
    });
  }, []);

  useEffect(() => {
    if (!circularLayout) return;
    const el = diskViewportRef.current;
    if (!el) return;
    const fn = (ev: WheelEvent) => applyDiskWheel(ev);
    el.addEventListener('wheel', fn, { passive: false });
    return () => el.removeEventListener('wheel', fn);
  }, [circularLayout, applyDiskWheel]);

  const onDiskPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const p = diskPanRef.current;
    diskDragRef.current = {
      active: true,
      px: e.clientX,
      py: e.clientY,
      ox: p.x,
      oy: p.y,
    };
  }, []);

  const onDiskPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (!diskDragRef.current.active) return;
    const d = diskDragRef.current;
    const dx = e.clientX - d.px;
    const dy = e.clientY - d.py;
    setDiskPan({ x: d.ox + dx, y: d.oy + dy });
  }, []);

  const onDiskPointerUp = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (diskDragRef.current.active) {
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    }
    diskDragRef.current.active = false;
  }, []);

  const cols = disk.length > 256 ? 32 : 16;
  const gridClass = cols === 32
    ? 'grid-cols-[repeat(32,minmax(0,1fr))]'
    : 'grid-cols-16';

  const n = disk.length;
  const polar = useMemo(() => getPolarDims(n), [n]);
  const { tracks, sectors } = polar;

  const cx = 50;
  const cy = 50;
  const rOuter = 48;
  const rHub = 10;
  const rSpan = rOuter - rHub;
  const startAngle = -Math.PI / 2;

  const gridLines = useMemo(() => {
    const circles: { r: number; key: string }[] = [];
    for (let t = 0; t <= tracks; t++) {
      const r = rHub + (t / tracks) * rSpan;
      circles.push({ r, key: `c-${t}` });
    }
    const radials: { a0: number; key: string }[] = [];
    for (let s = 0; s <= sectors; s++) {
      const a0 = startAngle + (s / sectors) * Math.PI * 2;
      radials.push({ a0, key: `r-${s}` });
    }
    return { circles, radials };
  }, [tracks, sectors]);

  return (
    <div className="w-full space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h3 className="text-sm font-semibold tracking-wider uppercase text-muted-foreground">
          Disk Block Map
          <span className="ml-2 text-xs font-normal text-muted-foreground/60">
            ({disk.length} blocks)
          </span>
        </h3>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
          <div className="flex items-center gap-2">
            <Switch
              id="disk-map-circular"
              checked={circularLayout}
              onCheckedChange={(on) => {
                setCircularLayout(on);
                if (on) {
                  setDiskZoom(1);
                  setDiskPan({ x: 0, y: 0 });
                }
              }}
            />
            <Label htmlFor="disk-map-circular" className="cursor-pointer text-xs font-normal text-muted-foreground">
              Circular map
            </Label>
          </div>
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-secondary" /> Free</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-primary/70" /> Used</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-danger" /> Corrupt</span>
            <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-warning/60" /> Reserved</span>
          </div>
        </div>
      </div>

      {circularLayout ? (
        <div className="w-full rounded-lg bg-background border border-border p-3">
          <div className="flex w-full items-center justify-between gap-2 pb-2">
            <p className="text-[10px] text-muted-foreground/80 font-mono tracking-wide">
              {tracks} tracks × {sectors} sectors · wheel zoom · drag pan
            </p>
            <button
              type="button"
              onClick={resetDiskView}
              className="shrink-0 rounded border border-border bg-secondary/40 px-2 py-0.5 text-[10px] font-mono text-muted-foreground hover:bg-secondary/70"
            >
              Reset view
            </button>
          </div>
          {/* Full-width rectangle; circular disk is largest square that fits (centered) */}
          <div
            ref={diskViewportRef}
            className="relative flex h-[min(28rem,420px,70vw)] w-full min-h-0 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-muted/20 touch-none select-none cursor-grab active:cursor-grabbing"
            onPointerDown={onDiskPointerDown}
            onPointerMove={onDiskPointerMove}
            onPointerUp={onDiskPointerUp}
            onPointerCancel={onDiskPointerUp}
            onLostPointerCapture={onDiskPointerUp}
          >
            <div className="relative aspect-square h-full max-h-full w-auto max-w-full min-h-0 min-w-0 overflow-hidden">
              <div
                className="absolute inset-0 will-change-transform"
                style={{
                  transform: `translate(${diskPan.x}px, ${diskPan.y}px) scale(${diskZoom})`,
                  transformOrigin: 'center center',
                }}
              >
                <svg
                  viewBox="0 0 100 100"
                  className="h-full w-full"
                  preserveAspectRatio="xMidYMid meet"
                  role="img"
                  aria-label={`Circular disk map, ${n} blocks in ${tracks} tracks and ${sectors} sectors`}
                >
                <title>Disk platter map: {tracks} tracks × {sectors} sectors</title>
                {disk.map((block) => {
                  const track = Math.floor(block.id / sectors);
                  const sector = block.id % sectors;
                  const r0 = rHub + (track / tracks) * rSpan;
                  const r1 = rHub + ((track + 1) / tracks) * rSpan;
                  const a0 = startAngle + (sector / sectors) * Math.PI * 2;
                  const a1 = startAngle + ((sector + 1) / sectors) * Math.PI * 2;
                  const isHighlighted =
                    (highlightFile && block.fileId === highlightFile)
                    || (hoveredFileId && block.fileId === hoveredFileId);
                  const ext = block as ExtendedDiskBlock;
                  const title = `Block ${block.id} (track ${track}, sector ${sector}): ${block.state}${block.fileId ? ` (${block.fileId})` : ''} - ${ext.allocStrategy || 'none'}`;

                  return (
                    <path
                      key={block.id}
                      d={wedgePath(cx, cy, r0, r1, a0, a1)}
                      fill={stateSvgFills[block.state]}
                      stroke={isHighlighted ? 'hsl(0 0% 100%)' : 'none'}
                      strokeWidth={isHighlighted ? 0.65 : 0}
                      strokeLinejoin="round"
                      vectorEffect="non-scaling-stroke"
                      className={`transition-[filter] duration-150 ${
                        block.state === 'corrupted' ? 'animate-pulse' : ''
                      }`}
                      style={{
                        filter: isHighlighted
                          ? 'brightness(1.65) saturate(1.15) contrast(1.05) drop-shadow(0 0 4px hsl(0 0% 100% / 0.55))'
                          : undefined,
                      }}
                      onMouseEnter={() => block.fileId && setHoveredFileId(block.fileId)}
                      onMouseLeave={() => setHoveredFileId(null)}
                    >
                      <title>{title}</title>
                    </path>
                  );
                })}

                {gridLines.circles.map(({ r, key }) => (
                  <circle
                    key={key}
                    cx={cx}
                    cy={cy}
                    r={r}
                    fill="none"
                    stroke="hsl(var(--foreground))"
                    strokeWidth={r <= rHub + 0.01 ? 0.35 : 0.22}
                    vectorEffect="non-scaling-stroke"
                  />
                ))}

                {gridLines.radials.map(({ a0, key }) => {
                  const x1 = cx + rHub * Math.cos(a0);
                  const y1 = cy + rHub * Math.sin(a0);
                  const x2 = cx + rOuter * Math.cos(a0);
                  const y2 = cy + rOuter * Math.sin(a0);
                  return (
                    <line
                      key={key}
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke="hsl(var(--foreground))"
                      strokeWidth={0.55}
                      vectorEffect="non-scaling-stroke"
                    />
                  );
                })}

                <circle
                  cx={cx}
                  cy={cy}
                  r={rHub * 0.92}
                  fill="hsl(var(--card))"
                  stroke="hsl(var(--foreground))"
                  strokeWidth={0.35}
                  vectorEffect="non-scaling-stroke"
                />
              </svg>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className={`grid ${gridClass} gap-[1px] p-3 rounded-lg bg-background border border-border`}>
          {disk.map((block) => {
            const isHighlighted = (highlightFile && block.fileId === highlightFile) || (hoveredFileId && block.fileId === hoveredFileId);
            return (
              <motion.div
                key={block.id}
                onMouseEnter={() => block.fileId ? setHoveredFileId(block.fileId) : null}
                onMouseLeave={() => setHoveredFileId(null)}
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{
                  scale: isHighlighted ? 1.3 : 1,
                  opacity: 1,
                }}
                transition={{ duration: 0.1, delay: Math.min(block.id * 0.0005, 0.5) }}
                className={`relative flex items-center justify-center aspect-[4/1] w-full rounded-[1px] transition-all duration-200 ${stateColors[block.state]} ${
                  isHighlighted ? 'ring-1 ring-foreground glow-green z-10' : ''
                } ${block.state === 'corrupted' ? 'animate-pulse' : ''}`}
                title={`Block ${block.id}: ${block.state}${block.fileId ? ` (${block.fileId})` : ''} - ${(block as ExtendedDiskBlock).allocStrategy || 'none'}`}
              >
                {(block as ExtendedDiskBlock).allocStrategy === 'linked' && block.state === 'used' && block.nextBlock !== null && (
                  <div className="absolute -right-[3px] z-10 opacity-60">
                    <svg width="6" height="6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-foreground">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </div>
                )}
                {(block as ExtendedDiskBlock).allocStrategy === 'indexed' && block.state === 'used' && block.fragment === 0 && (
                  <div className="absolute inset-0 bg-secondary/40 border border-secondary" title="Index Block Indicator" />
                )}
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
