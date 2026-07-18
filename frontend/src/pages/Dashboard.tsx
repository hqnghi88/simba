import React, { useState, useEffect, useMemo } from 'react';
import {
  Chart as ChartJS,
  RadialLinearScale,
  LinearScale,
  CategoryScale,
  PointElement,
  LineElement,
  BarElement,
  RadarController,
  BarController,
  Filler,
  Tooltip as ChartTooltip,
  Legend,
} from 'chart.js';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

// Safe chart wrapper that properly destroys old instances
function SafeChart({
  type,
  data,
  options,
  id,
}: {
  type: 'bar' | 'radar';
  data: any;
  options?: any;
  id: string;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const chartRef = React.useRef<ChartJS | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    // Destroy previous instance
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }
    chartRef.current = new ChartJS(canvasRef.current, {
      type,
      data,
      options: { responsive: true, maintainAspectRatio: false, ...options },
    });
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [type, data, options]);

  return <canvas ref={canvasRef} id={id} />;
}

ChartJS.register(
  RadialLinearScale,
  LinearScale,
  CategoryScale,
  PointElement,
  LineElement,
  BarElement,
  RadarController,
  BarController,
  Filler,
  ChartTooltip,
  Legend
);

// --- Constants ---
const GROUPS = ['Worse \u2013 off', 'Better \u2013 off', 'Cooperative', 'Independent'] as const;
type Group = (typeof GROUPS)[number];

const GROUP_COLORS: Record<Group, string> = {
  'Worse \u2013 off': '#d97706',
  'Better \u2013 off': '#0284c7',
  Cooperative: '#16a34a',
  Independent: '#7c3aed',
};

const GROUP_BG: Record<Group, string> = {
  'Worse \u2013 off': 'rgba(217,119,6,0.15)',
  'Better \u2013 off': 'rgba(2,132,199,0.15)',
  Cooperative: 'rgba(22,163,74,0.15)',
  Independent: 'rgba(124,58,237,0.15)',
};

const KPI_ORDER = [
  'Productivity',
  'Value added',
  'Income',
  'Soil quality',
  'Exposure to pesticides',
  "Women's empowerment",
  "Youth empowerment",
  'Adaptive capacity',
  'Social Justice',
  'Human well-being',
  'Nutrient management',
  'Crop health',
  'Water sources',
];

const KPI_COLORS: Record<string, string> = {
  Productivity: '#16a34a',
  'Value added': '#0284c7',
  Income: '#d97706',
  'Soil quality': '#92400e',
  'Exposure to pesticides': '#dc2626',
  "Women's empowerment": '#db2777',
  "Youth empowerment": '#9333ea',
  'Adaptive capacity': '#0891b2',
  'Social Justice': '#4f46e5',
  'Human well-being': '#059669',
  'Nutrient management': '#ca8a04',
  'Crop health': '#15803d',
  'Water sources': '#0369a1',
};

const CHAIN_COLORS = ['#0284c7', '#16a34a', '#d97706', '#7c3aed'];

// --- Data types ---
interface KpiRow {
  kpi: string;
  indicator: string;
  unit: string;
  group: Group;
  median: number | null;
  p25: number | null;
  p75: number | null;
  rate: number | null;
}

interface IndGroup {
  indicator: string;
  unit: string;
  kpi: string;
  groups: Partial<Record<Group, { m: number | null; p25: number | null; p75: number | null; r: number | null }>>;
}

// --- Helpers ---
function fmt(v: number | null | undefined): string {
  if (v == null) return '\u2014';
  return Number.isInteger(v) ? String(v) : v.toFixed(1);
}

function byKPI(items: KpiRow[]): Record<string, KpiRow[]> {
  const m: Record<string, KpiRow[]> = {};
  items.forEach((d) => {
    if (!m[d.kpi]) m[d.kpi] = [];
    m[d.kpi].push(d);
  });
  return m;
}

function byInd(items: KpiRow[]): IndGroup[] {
  const m: Record<string, IndGroup> = {};
  items.forEach((d) => {
    if (!m[d.indicator])
      m[d.indicator] = { indicator: d.indicator, unit: d.unit, kpi: d.kpi, groups: {} };
    m[d.indicator].groups[d.group] = {
      m: d.median,
      p25: d.p25,
      p75: d.p75,
      r: d.rate,
    };
  });
  return Object.values(m);
}

// --- Sub-components ---

function GroupBadge({ group }: { group: Group }) {
  const colorMap: Record<Group, string> = {
    Cooperative: 'bg-green-100 text-green-800 border-green-200',
    Independent: 'bg-purple-100 text-purple-800 border-purple-200',
    'Better \u2013 off': 'bg-blue-100 text-blue-800 border-blue-200',
    'Worse \u2013 off': 'bg-amber-100 text-amber-800 border-amber-200',
  };
  return (
    <Badge variant="outline" className={colorMap[group]}>
      {group}
    </Badge>
  );
}

function IndCard({ ind, idx }: { ind: IndGroup; idx: number }) {
  const chartId = `chart-${ind.indicator.replace(/[^a-z]/gi, '')}-${idx}`;
  const hasNum = Object.values(ind.groups).some((g) => g?.m != null && !isNaN(g.m));

  const chartData = useMemo(() => {
    if (!hasNum) return null;
    return {
      labels: GROUPS.map((g) => g.split(' ')[0]),
      datasets: [
        {
          data: GROUPS.map((g) => ind.groups[g]?.m || 0),
          backgroundColor: GROUPS.map((g) => GROUP_BG[g]),
          borderColor: GROUPS.map((g) => GROUP_COLORS[g]),
          borderWidth: 1.5,
        },
      ],
    };
  }, [ind, hasNum]);

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: '#475569', font: { size: 10 } },
          grid: { display: false },
        },
        y: {
          ticks: { color: '#64748b' },
          grid: { color: '#f1f5f9' },
        },
      },
    }),
    []
  );

  return (
    <Card className="mb-3">
      <CardContent className="pt-4 pb-3">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <p className="text-sm font-semibold text-foreground">{ind.indicator}</p>
            <p className="text-xs text-muted-foreground mb-2">{ind.unit}</p>
            {hasNum && chartData ? (
              <div className="h-[160px]">
                <SafeChart id={chartId} type="bar" data={chartData} options={chartOptions} />
              </div>
            ) : (
              <div className="space-y-1">
                {GROUPS.map((g) => {
                  const v = ind.groups[g]?.r;
                  if (v == null) return null;
                  const allRates = GROUPS.map((gg) => ind.groups[gg]?.r ?? 0);
                  const mx = Math.max(...allRates, 1);
                  const w = (v / mx) * 100;
                  return (
                    <div key={g} className="flex items-center gap-2 text-xs">
                      <span className="w-[60px] text-right text-muted-foreground">
                        {g.split(' ')[0]}
                      </span>
                      <div className="flex-1 h-3.5 bg-muted rounded-sm border border-border overflow-hidden">
                        <div
                          className="h-full rounded-sm"
                          style={{ width: `${w}%`, backgroundColor: GROUP_COLORS[g] }}
                        />
                      </div>
                      <span className="w-10 font-semibold">{fmt(v)}%</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-[10px] uppercase">Group</TableHead>
                  <TableHead className="text-[10px] uppercase">Median</TableHead>
                  <TableHead className="text-[10px] uppercase">P25\u2013P75</TableHead>
                  <TableHead className="text-[10px] uppercase">Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {GROUPS.map((g) => {
                  const v = ind.groups[g];
                  if (!v) return null;
                  const range =
                    v.p25 != null && v.p75 != null ? `${fmt(v.p25)}\u2013${fmt(v.p75)}` : '\u2014';
                  return (
                    <TableRow key={g}>
                      <TableCell>
                        <GroupBadge group={g} />
                      </TableCell>
                      <TableCell className="font-semibold">{fmt(v.m)}</TableCell>
                      <TableCell className="text-muted-foreground">{range}</TableCell>
                      <TableCell>{fmt(v.r)}</TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// --- Radar Chart (Overview) ---
function RevenueRadar({ data }: { data: Record<string, KpiRow[]> }) {
  const chains = Object.keys(data);
  const chartData = useMemo(() => {
    return {
      labels: GROUPS.map((g) => g.split(' ')[0]),
      datasets: chains.map((n, i) => {
        const bi = byInd(data[n]);
        const rev = bi.find((d) => /revenue/i.test(d.indicator) && !/\(/.test(d.indicator));
        return {
          label: n,
          data: GROUPS.map((g) => rev?.groups[g]?.m || 0),
          backgroundColor: CHAIN_COLORS[i] + '22',
          borderColor: CHAIN_COLORS[i],
          borderWidth: 2,
        };
      }),
    };
  }, [data]);

  const options = useMemo(
    () => ({
      responsive: true,
      plugins: { legend: { labels: { color: '#475569', font: { size: 11 } } } },
      scales: {
        r: {
          ticks: { color: '#64748b', backdropColor: 'transparent' },
          grid: { color: 'rgba(226,232,240,0.9)' },
          pointLabels: { color: '#475569', font: { size: 10 } },
        },
      },
    }),
    []
  );

  return <SafeChart id="revenue-radar" type="radar" data={chartData} options={options} />;
}

// --- Gap Chart (Overview) ---
function GapChart({ data }: { data: Record<string, KpiRow[]> }) {
  const chains = Object.keys(data);
  const chartData = useMemo(() => {
    const labels: string[] = [];
    const values: number[] = [];
    const colors: string[] = [];
    chains.forEach((n) => {
      const bi = byInd(data[n]);
      const profit = bi.find(
        (d) => /profit/i.test(d.indicator) && !/income/i.test(d.indicator) && !/\(/.test(d.indicator)
      );
      const rev = bi.find((d) => /revenue/i.test(d.indicator) && !/\(/.test(d.indicator));
      if (profit) {
        const cv = profit.groups['Cooperative']?.m || 0;
        const iv = profit.groups['Independent']?.m || 0;
        labels.push(n + ': Profit');
        values.push(cv - iv);
        colors.push(cv >= iv ? 'rgba(22,163,74,0.6)' : 'rgba(220,38,38,0.6)');
      }
      if (rev) {
        const cv = rev.groups['Cooperative']?.m || 0;
        const iv = rev.groups['Independent']?.m || 0;
        labels.push(n + ': Revenue');
        values.push(cv - iv);
        colors.push(cv >= iv ? 'rgba(22,163,74,0.6)' : 'rgba(220,38,38,0.6)');
      }
    });
    return {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderColor: colors.map((c) => c.replace('.6', '.9')), borderWidth: 1 }],
    };
  }, [data]);

  const options = useMemo(
    () => ({
      responsive: true,
      indexAxis: 'y' as const,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#475569' }, grid: { color: '#e2e8f0' } },
        y: { ticks: { color: '#475569', font: { size: 10 } } },
      },
    }),
    []
  );

  return <SafeChart id="gap-chart" type="bar" data={chartData} options={options} />;
}

// --- Chain Tab ---
function ChainTab({ name, items }: { name: string; items: KpiRow[] }) {
  const bk = useMemo(() => byKPI(items), [items]);
  const inds = useMemo(() => {
    const result: Record<string, IndGroup[]> = {};
    KPI_ORDER.forEach((k) => {
      const kpiItems = bk[k];
      result[k] = kpiItems ? byInd(kpiItems) : [];
    });
    return result;
  }, [bk]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        {KPI_ORDER.map((k) => {
          const cnt = inds[k]?.length || 0;
          return (
            <div
              key={k}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border ${
                cnt === 0 ? 'opacity-40 border-border' : 'border-border bg-white'
              }`}
            >
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: KPI_COLORS[k] }}
              />
              <span className="font-semibold">{k}</span>
              <span className="text-muted-foreground">({cnt})</span>
            </div>
          );
        })}
      </div>

      {KPI_ORDER.map((kpiName) => {
        const kpiItems = inds[kpiName];
        const cnt = kpiItems?.length || 0;
        return (
          <div key={kpiName}>
            <Card className="mb-2">
              <CardHeader className="py-2 px-4 flex flex-row items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: KPI_COLORS[kpiName] }}
                />
                <CardTitle className="text-sm">{kpiName}</CardTitle>
                <span className="ml-auto text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                  {cnt > 0 ? `${cnt} indicators` : 'No data'}
                </span>
              </CardHeader>
            </Card>
            {cnt === 0 ? (
              <div className="text-center text-muted-foreground text-sm py-8 border border-dashed border-border rounded-lg mb-3">
                No data available for {kpiName} in {name}
              </div>
            ) : (
              kpiItems.map((ind, i) => <IndCard key={ind.indicator} ind={ind} idx={i} />)
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- Cross-Chain Tab ---
function CrossChainTab({ data }: { data: Record<string, KpiRow[]> }) {
  const chains = Object.keys(data);
  return (
    <div className="space-y-4">
      {KPI_ORDER.map((kpiName) => {
        const hasData = chains.some((n) => byKPI(data[n])[kpiName]);
        if (!hasData) return null;
        return (
          <div key={kpiName}>
            <Card className="mb-2">
              <CardHeader className="py-2 px-4 flex flex-row items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: KPI_COLORS[kpiName] }}
                />
                <CardTitle className="text-sm">
                  {kpiName} \u2014 Across Chains
                </CardTitle>
              </CardHeader>
            </Card>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-[10px] uppercase">Chain</TableHead>
                    <TableHead className="text-[10px] uppercase">Indicator</TableHead>
                    <TableHead className="text-[10px] uppercase">Unit</TableHead>
                    <TableHead className="text-[10px] uppercase">Worse-off</TableHead>
                    <TableHead className="text-[10px] uppercase">Better-off</TableHead>
                    <TableHead className="text-[10px] uppercase">Coop</TableHead>
                    <TableHead className="text-[10px] uppercase">Indep</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {chains.map((ch) => {
                    const bk = byKPI(data[ch]);
                    if (!bk[kpiName]) return null;
                    const bi = byInd(bk[kpiName]);
                    return bi.map((m, i) => (
                      <TableRow key={`${ch}-${m.indicator}`}>
                        {i === 0 && (
                          <TableCell
                            rowSpan={bi.length}
                            className="font-semibold whitespace-nowrap"
                          >
                            {ch}
                          </TableCell>
                        )}
                        <TableCell>{m.indicator}</TableCell>
                        <TableCell className="text-muted-foreground whitespace-nowrap">
                          {m.unit}
                        </TableCell>
                        {GROUPS.map((g) => (
                          <TableCell key={g} className="font-medium">
                            {fmt(m.groups[g]?.m)}
                          </TableCell>
                        ))}
                      </TableRow>
                    ));
                  })}
                </TableBody>
              </Table>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// --- Main Dashboard ---
export default function Dashboard() {
  const [data, setData] = useState<Record<string, KpiRow[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/kpi_data.json')
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        console.error('Failed to load KPI data', e);
        setLoading(false);
      });
  }, []);

  const chains = useMemo(() => Object.keys(data), [data]);

  // Compute insights
  const insights = useMemo(() => {
    const result: { tag: string; tagColor: string; title: string; text: string }[] = [];
    chains.forEach((n) => {
      const bi = byInd(data[n]);
      const profit = bi.find(
        (d) => /profit/i.test(d.indicator) && !/income/i.test(d.indicator) && !/\(/.test(d.indicator)
      );
      const farmInc = bi.find((d) => /^farm income$/i.test(d.indicator));
      if (profit) {
        const cv = profit.groups['Cooperative']?.m;
        const iv = profit.groups['Independent']?.m;
        if (cv != null && iv != null) {
          const diff = ((cv - iv) / iv * 100).toFixed(0);
          result.push({
            tag: 'Profit',
            tagColor: 'bg-green-100 text-green-800',
            title: `${n}: Coop vs Independent gap`,
            text: `Coop ${fmt(cv)}M vs ${fmt(iv)}M independent (${diff >= '0' ? '+' : ''}${diff}%).`,
          });
        }
      }
      if (farmInc) {
        const b = farmInc.groups['Better \u2013 off']?.m;
        const w = farmInc.groups['Worse \u2013 off']?.m;
        if (b != null && w != null) {
          result.push({
            tag: 'Income',
            tagColor: 'bg-blue-100 text-blue-800',
            title: `${n}: Income gap`,
            text: `Better-off ${fmt(b)}M vs worse-off ${fmt(w)}M (${(b / w).toFixed(1)}x).`,
          });
        }
      }
    });
    return result;
  }, [data, chains]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center text-muted-foreground">
        Loading KPI data...
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-5 bg-slate-50 min-h-screen">
      <Tabs defaultValue="overview">
        <div className="bg-white border border-border rounded-lg shadow-sm sticky top-0 z-50">
          <TabsList className="h-auto p-1 bg-transparent w-full justify-start rounded-none overflow-x-auto">
            <TabsTrigger value="overview" className="rounded-md">
              Overview
            </TabsTrigger>
            {chains.map((n) => (
              <TabsTrigger key={n} value={n} className="rounded-md">
                {n}
              </TabsTrigger>
            ))}
            <TabsTrigger value="compare" className="rounded-md">
              Cross-Chain
            </TabsTrigger>
          </TabsList>
        </div>

        {/* --- Overview Tab --- */}
        <TabsContent value="overview" className="mt-4 space-y-5">
          {/* Hero cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {chains.map((n, i) => {
              const bi = byInd(data[n]);
              const profit = bi.find(
                (d) =>
                  /profit/i.test(d.indicator) &&
                  !/income/i.test(d.indicator) &&
                  !/\(/.test(d.indicator)
              );
              const cv = profit?.groups['Cooperative']?.m || 0;
              const iv = profit?.groups['Independent']?.m || 0;
              const diff = cv - iv;
              return (
                <Card
                  key={n}
                  className="relative overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
                  style={{ borderTop: `3px solid ${CHAIN_COLORS[i]}` }}
                >
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{n}</p>
                    <p className="text-3xl font-bold text-foreground">{fmt(cv)}M</p>
                    <p className="text-xs text-muted-foreground">
                      Cooperative profit (mill. VN\u0110/ha/yr)
                    </p>
                    {diff !== 0 && (
                      <p
                        className={`text-sm font-semibold mt-1 ${
                          diff >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}
                      >
                        {diff >= 0 ? '+' : ''}
                        {fmt(Math.abs(diff))} vs Independent
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Insights */}
          <div>
            <h3 className="text-base font-bold text-foreground mb-3 flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: '#0284c7' }}
              />
              Key Insights
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
              {insights.map((ins, i) => (
                <Card key={i}>
                  <CardContent className="pt-4">
                    <Badge
                      className={`${ins.tagColor} border-transparent text-[10px] font-semibold mb-2`}
                    >
                      {ins.tag}
                    </Badge>
                    <p className="text-sm font-semibold text-foreground">{ins.title}</p>
                    <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                      {ins.text}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* Charts */}
          <div>
            <h3 className="text-base font-bold text-foreground mb-3 flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: '#7c3aed' }}
              />
              Chain Comparison
            </h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-purple-500" />
                    Revenue by Group
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[220px]">
                    <RevenueRadar data={data} />
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-green-500" />
                    Cooperative vs Independent Gap
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[220px]">
                    <GapChart data={data} />
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Chain CTA cards */}
          <div>
            <h3 className="text-base font-bold text-foreground mb-3 flex items-center gap-2">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: '#0284c7' }}
              />
              Explore Each Chain
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {chains.map((n, i) => {
                const bk = byKPI(data[n]);
                const indCnt = byInd(data[n]).length;
                return (
                  <Card
                    key={n}
                    className="cursor-pointer hover:shadow-md transition-shadow"
                    style={{ borderTop: `3px solid ${CHAIN_COLORS[i]}` }}
                  >
                    <CardContent className="pt-4">
                      <p className="text-xs text-muted-foreground">{n}</p>
                      <p className="text-xl font-bold text-foreground">13 KPIs</p>
                      <p className="text-xs text-muted-foreground">
                        {indCnt} indicators with data \u00b7 {data[n].length} data points
                      </p>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        </TabsContent>

        {/* --- Chain Tabs --- */}
        {chains.map((n) => (
          <TabsContent key={n} value={n} className="mt-4">
            <ChainTab name={n} items={data[n]} />
          </TabsContent>
        ))}

        {/* --- Cross-Chain Tab --- */}
        <TabsContent value="compare" className="mt-4">
          <CrossChainTab data={data} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
