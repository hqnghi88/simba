import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { extractKPIs, applyKPIs } from '@/lib/api';
import { ArrowLeft, CheckCircle2, Loader2, Sparkles } from 'lucide-react';

interface PendingEntry {
  id: string;
  chain: string;
  kpi: string;
  indicator: string;
  unit: string;
  group: string;
  median: number | null;
  p25: number | null;
  p75: number | null;
  rate: number | null;
  baseline_median: number | null;
  baseline_p25: number | null;
  baseline_p75: number | null;
  baseline_rate: number | null;
  is_new: boolean;
  approved: boolean;
}

const CHAIN_ORDER = ['Mango', 'Rice-lotus', 'Rice - shrimp', 'Coconut'];
const KPI_ORDER = [
  'Productivity', 'Value added', 'Income', 'Soil quality',
  'Exposure to pesticides', "Women's empowerment", "Youth empowerment",
  'Adaptive capacity', 'Social Justice', 'Human well-being',
  'Nutrient management', 'Crop health', 'Water sources',
];

const CHAIN_COLORS: Record<string, string> = {
  Mango: '#f59e0b',
  'Rice-lotus': '#10b981',
  'Rice - shrimp': '#3b82f6',
  Coconut: '#8b5cf6',
};

function formatVal(v: number | null): string {
  if (v === null || v === undefined) return '—';
  return v % 1 === 0 ? v.toString() : v.toFixed(1);
}

function ValueDiff({
  current,
  proposed,
}: {
  current: number | null;
  proposed: number | null;
}) {
  const changed =
    current !== null && proposed !== null && current !== proposed;
  const isNew = current === null && proposed !== null;

  return (
    <span className="flex items-center gap-1.5 text-sm">
      <span className="text-muted-foreground">{formatVal(current)}</span>
      <span className="text-xs">→</span>
      <span
        className={
          isNew
            ? 'text-green-600 font-medium'
            : changed
            ? 'text-amber-600 font-medium'
            : 'text-foreground'
        }
      >
        {formatVal(proposed)}
      </span>
      {isNew && (
        <Badge variant="outline" className="text-[10px] border-green-300 text-green-700 ml-1">
          NEW
        </Badge>
      )}
      {changed && (
        <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700 ml-1">
          CHANGED
        </Badge>
      )}
    </span>
  );
}

export default function KPIReview() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState('');
  const [entries, setEntries] = useState<PendingEntry[]>([]);
  const [sourceDocs, setSourceDocs] = useState<string[]>([]);
  const [filterChain, setFilterChain] = useState<string>('all');
  const [filterKpi, setFilterKpi] = useState<string>('all');
  const [emptyEntriesMsg, setEmptyEntriesMsg] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const data = await extractKPIs();
        if (cancelled) return;
        setPendingId(data.pending_id);
        setEntries(data.entries || []);
        setSourceDocs(data.source_doc_ids || []);
        if (!data.entries || data.entries.length === 0) {
          if (!cancelled) {
            setEmptyEntriesMsg(true);
            setTimeout(() => navigate('/'), 2000);
          }
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message || 'Extraction failed');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const toggle = (id: string) => {
    setEntries(prev =>
      prev.map(e => (e.id === id ? { ...e, approved: !e.approved } : e))
    );
  };

  const toggleChain = (chain: string, val: boolean) => {
    const changedIds = new Set(changedEntries.map(e => e.id));
    setEntries(prev =>
      prev.map(e => (changedIds.has(e.id) && e.chain === chain ? { ...e, approved: val } : e))
    );
  };

  const toggleKpi = (kpi: string, val: boolean) => {
    const changedIds = new Set(changedEntries.map(e => e.id));
    setEntries(prev =>
      prev.map(e => (changedIds.has(e.id) && e.kpi === kpi ? { ...e, approved: val } : e))
    );
  };

  const toggleAll = (val: boolean) => {
    const changedIds = new Set(changedEntries.map(e => e.id));
    setEntries(prev =>
      prev.map(e => (changedIds.has(e.id) ? { ...e, approved: val } : e))
    );
  };

  const hasChanges = (e: PendingEntry): boolean => {
    const hasAny = (o: PendingEntry) =>
      o.median !== null || o.p25 !== null || o.p75 !== null || o.rate !== null;
    if (e.is_new) return hasAny(e);
    const differs = (proposed: number | null, base: number | null) =>
      proposed !== null && proposed !== base;
    return (
      differs(e.median, e.baseline_median) ||
      differs(e.p25, e.baseline_p25) ||
      differs(e.p75, e.baseline_p75) ||
      differs(e.rate, e.baseline_rate)
    );
  };

  const changedEntries = useMemo(() => entries.filter(hasChanges), [entries]);

  const filtered = useMemo(() => {
    return changedEntries.filter(e => {
      if (filterChain !== 'all' && e.chain !== filterChain) return false;
      if (filterKpi !== 'all' && e.kpi !== filterKpi) return false;
      return true;
    });
  }, [changedEntries, filterChain, filterKpi]);

  const approvedCount = changedEntries.filter(e => e.approved).length;
  const totalCount = changedEntries.length;

  const chains = useMemo(() => {
    const s = new Set(changedEntries.map(e => e.chain));
    return CHAIN_ORDER.filter(c => s.has(c));
  }, [changedEntries]);

  const kpis = useMemo(() => {
    const s = new Set(changedEntries.map(e => e.kpi));
    return KPI_ORDER.filter(k => s.has(k));
  }, [changedEntries]);

  const grouped = useMemo(() => {
    const map = new Map<string, Map<string, PendingEntry[]>>();
    for (const e of filtered) {
      if (!map.has(e.chain)) map.set(e.chain, new Map());
      const kpiMap = map.get(e.chain)!;
      if (!kpiMap.has(e.kpi)) kpiMap.set(e.kpi, []);
      kpiMap.get(e.kpi)!.push(e);
    }
    return map;
  }, [filtered]);

  const handleApply = async () => {
    const approvedIds = entries.filter(e => e.approved).map(e => e.id);
    if (approvedIds.length === 0) return;
    try {
      setApplying(true);
      await applyKPIs(pendingId, approvedIds);
      navigate('/');
    } catch (e: any) {
      setError(e.message || 'Apply failed');
      setApplying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-muted-foreground">
          Extracting KPIs from documents... This may take a minute.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <p className="text-destructive text-lg">{error}</p>
        <Button variant="outline" onClick={() => navigate('/')}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to Dashboard
        </Button>
      </div>
    );
  }

  if (emptyEntriesMsg) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
        <p className="text-muted-foreground text-lg">No enabled documents found. KPIs reset to baseline.</p>
        <p className="text-sm text-muted-foreground">Redirecting...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back
          </Button>
          <Separator orientation="vertical" className="h-6" />
          <div>
            <h1 className="text-lg font-semibold flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-amber-500" />
              KPI Extraction Review
            </h1>
            <p className="text-sm text-muted-foreground">
              {sourceDocs.length > 0 && `From: ${sourceDocs.join(', ')} · `}
              {totalCount} changes found ·{' '}
              <span className="text-green-600 font-medium">{approvedCount} approved</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => navigate('/')}>
            Cancel
          </Button>
          <Button
            onClick={handleApply}
            disabled={applying || approvedCount === 0}
            className="min-w-[160px]"
          >
            {applying ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Applying...
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Apply Selected ({approvedCount})
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3 px-6 py-3 border-b bg-muted/30">
        <Button
          variant={filterChain === 'all' && filterKpi === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => { toggleAll(true); setFilterChain('all'); setFilterKpi('all'); }}
        >
          Select All
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => toggleAll(false)}
        >
          Deselect All
        </Button>
        <Separator orientation="vertical" className="h-6" />
        <Select value={filterChain} onValueChange={setFilterChain}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All Chains" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Chains</SelectItem>
            {chains.map(c => (
              <SelectItem key={c} value={c}>{c}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filterKpi} onValueChange={setFilterKpi}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {kpis.map(k => (
              <SelectItem key={k} value={k}>{k}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Entries */}
      <ScrollArea className="flex-1 px-6 py-4">
        {totalCount === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            No KPI entries were extracted from the documents.
          </div>
        ) : (
          <div className="space-y-6">
            {CHAIN_ORDER.filter(c => grouped.has(c)).map(chain => {
              const kpiMap = grouped.get(chain)!;
              const chainEntries = filtered.filter(e => e.chain === chain);
              const chainApproved = chainEntries.filter(e => e.approved).length;
              const allChainOn = chainEntries.length > 0 && chainApproved === chainEntries.length;

              return (
                <Card key={chain}>
                  <CardHeader className="py-3 px-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: CHAIN_COLORS[chain] || '#6b7280' }}
                        />
                        <CardTitle className="text-base">{chain}</CardTitle>
                        <Badge variant="secondary" className="text-xs">
                          {chainApproved}/{chainEntries.length}
                        </Badge>
                      </div>
                      <Switch
                        checked={allChainOn}
                        onCheckedChange={(v) => toggleChain(chain, v)}
                      />
                    </div>
                  </CardHeader>
                  <CardContent className="px-4 pb-4">
                    {KPI_ORDER.filter(k => kpiMap.has(k)).map(kpi => {
                      const kpiEntries = kpiMap.get(kpi)!;
                      const kpiApproved = kpiEntries.filter(e => e.approved).length;
                      const allKpiOn =
                        kpiEntries.length > 0 && kpiApproved === kpiEntries.length;

                      return (
                        <div key={kpi} className="mb-4 last:mb-0">
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-muted-foreground">
                              {kpi}
                            </span>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-[10px]">
                                {kpiApproved}/{kpiEntries.length}
                              </Badge>
                              <Switch
                                checked={allKpiOn}
                                onCheckedChange={(v) => toggleKpi(kpi, v)}
                                className="scale-75"
                              />
                            </div>
                          </div>
                          <Table>
                            <TableHeader>
                              <TableRow className="h-8">
                                <TableHead className="w-10 py-1"></TableHead>
                                <TableHead className="py-1 text-xs">Indicator</TableHead>
                                <TableHead className="py-1 text-xs">Group</TableHead>
                                <TableHead className="py-1 text-xs">Median</TableHead>
                                <TableHead className="py-1 text-xs">Rate</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {kpiEntries.map(entry => (
                                <TableRow
                                  key={entry.id}
                                  className={entry.approved ? '' : 'opacity-40'}
                                  onClick={() => toggle(entry.id)}
                                >
                                  <TableCell className="py-1 px-2">
                                    <Switch
                                      checked={entry.approved}
                                      onCheckedChange={() => toggle(entry.id)}
                                      className="scale-75"
                                      onClick={(e) => e.stopPropagation()}
                                    />
                                  </TableCell>
                                  <TableCell className="py-1 text-sm">
                                    {entry.indicator}
                                    {entry.is_new && (
                                      <Badge
                                        variant="outline"
                                        className="text-[9px] ml-1 border-green-300 text-green-700"
                                      >
                                        NEW
                                      </Badge>
                                    )}
                                  </TableCell>
                                  <TableCell className="py-1 text-sm">{entry.group}</TableCell>
                                  <TableCell className="py-1">
                                    <ValueDiff
                                      current={entry.baseline_median}
                                      proposed={entry.median}
                                    />
                                  </TableCell>
                                  <TableCell className="py-1">
                                    <ValueDiff
                                      current={entry.baseline_rate}
                                      proposed={entry.rate}
                                    />
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
