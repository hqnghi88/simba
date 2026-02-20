import React from 'react';
import { motion } from 'framer-motion';
import {
    Droplets,
    Thermometer,
    Wind,
    Sun,
    Sprout,
    Bug,
    BarChart3,
    TrendingUp,
    Activity,
    Trees,
    Info
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface KPIProps {
    title: string;
    value: string;
    unit: string;
    trend: 'up' | 'down' | 'neutral';
    change: string;
    icon: React.ElementType;
    color: string;
    explanation?: string;
}

const KPICard: React.FC<KPIProps & { delay: number }> = ({
    title, value, unit, trend, change, icon: Icon, color, delay, explanation
}) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay }}
        >
            <Card className="overflow-hidden hover:shadow-lg transition-shadow duration-300">
                <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                    <CardTitle className="text-sm font-medium text-muted-foreground flex items-center">
                        {title}
                        {explanation && (
                            <TooltipProvider>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Info className="h-3 w-3 ml-1.5 cursor-help opacity-50 hover:opacity-100 transition-opacity" />
                                    </TooltipTrigger>
                                    <TooltipContent side="top" className="max-w-[300px] p-3 text-xs leading-relaxed">
                                        <div className="space-y-1">
                                            <p className="font-semibold text-primary-foreground/90 border-b border-primary-foreground/20 pb-1 mb-1">Source Evidence</p>
                                            <p>{explanation}</p>
                                        </div>
                                    </TooltipContent>
                                </Tooltip>
                            </TooltipProvider>
                        )}
                    </CardTitle>
                    <div className={`p-2 rounded-full ${color} bg-opacity-10`}>
                        <Icon className={`h-4 w-4 ${color.replace('bg-', 'text-')}`} />
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="text-2xl font-bold">
                        {value}
                        <span className="text-xs font-normal text-muted-foreground ml-1">{unit}</span>
                    </div>
                    <div className="flex items-center mt-1">
                        {trend === 'up' ? (
                            <TrendingUp className="h-4 w-4 text-green-500 mr-1 shrink-0" />
                        ) : trend === 'down' ? (
                            <TrendingUp className="h-4 w-4 text-red-500 mr-1 rotate-180 shrink-0" />
                        ) : (
                            <Activity className="h-4 w-4 text-gray-500 mr-1 shrink-0" />
                        )}
                        <TooltipProvider>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <p className={`text-xs truncate cursor-default ${trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-gray-500'
                                        }`}>
                                        {change}
                                    </p>
                                </TooltipTrigger>
                                {change && (
                                    <TooltipContent side="bottom" className="max-w-[200px] text-[10px]">
                                        {change}
                                    </TooltipContent>
                                )}
                            </Tooltip>
                        </TooltipProvider>
                    </div>
                </CardContent>
            </Card>
        </motion.div>
    );
};

const Dashboard: React.FC = () => {
    const [loading, setLoading] = React.useState(true);
    const [recalculating, setRecalculating] = React.useState(false);
    const [kpiData, setKpiData] = React.useState<any>(null);

    const fetchKPIs = async () => {
        try {
            const { getDashboardKPIs } = await import('@/lib/api');
            const data = await getDashboardKPIs();
            setKpiData(data);
            setLoading(false);
            if (data.is_stale) {
                console.log("Dashboard data is stale, prompting user.");
            }
        } catch (e) {
            console.error("Failed to load dashboard data", e);
            setLoading(false);
        }
    };

    React.useEffect(() => {
        fetchKPIs();
    }, []);

    const handleRecalculate = async () => {
        setRecalculating(true);
        try {
            const { recalculateDashboardKPIs } = await import('@/lib/api');
            const data = await recalculateDashboardKPIs();
            setKpiData(data);
        } catch (e) {
            console.error("Recalculation failed", e);
        } finally {
            setRecalculating(false);
        }
    };

    const kpis: KPIProps[] = React.useMemo(() => {
        // Default / Mock if loading or error or empty
        const d = kpiData || {};

        return [
            {
                title: "Soil Moisture",
                value: d.soil_moisture || "N/A",
                unit: "%",
                trend: d.soil_moisture_trend as any || "neutral",
                change: d.soil_moisture_trend_reasoning || "Stable data",
                icon: Droplets,
                color: "text-blue-500",
                explanation: d.soil_moisture_explanation,
            },
            {
                title: "Temperature-Avg",
                value: d.temperature || "N/A",
                unit: "°C",
                trend: d.temperature_trend as any || "neutral",
                change: d.temperature_trend_reasoning || "Stable data",
                icon: Thermometer,
                color: "text-orange-500",
                explanation: d.temperature_explanation,
            },
            {
                title: "Rainfall",
                value: d.rainfall || "N/A",
                unit: "mm",
                trend: d.rainfall_trend as any || "neutral",
                change: d.rainfall_trend_reasoning || "Stable data",
                icon: CloudRainIcon,
                color: "text-blue-400",
                explanation: d.rainfall_explanation,
            },
            {
                title: "Humidity",
                value: d.humidity || "N/A",
                unit: "%",
                trend: d.humidity_trend as any || "neutral",
                change: d.humidity_trend_reasoning || "Stable data",
                icon: Wind,
                color: "text-cyan-500",
                explanation: d.humidity_explanation,
            },
            {
                title: "Crop Yield Forecast",
                value: d.crop_yield || "N/A",
                unit: "tons/ha",
                trend: d.crop_yield_trend as any || "neutral",
                change: d.crop_yield_trend_reasoning || "Stable data",
                icon: Sprout,
                color: "text-green-600",
                explanation: d.crop_yield_explanation,
            },
            {
                title: "Pest Risk Index",
                value: d.pest_risk || "N/A",
                unit: "",
                trend: d.pest_risk_trend as any || "neutral",
                change: d.pest_risk_trend_reasoning || "Stable data",
                icon: Bug,
                color: "text-red-500",
                explanation: d.pest_risk_explanation,
            },
            {
                title: "Fertilizer Usage",
                value: d.fertilizer || "N/A",
                unit: "kg",
                trend: d.fertilizer_trend as any || "neutral",
                change: d.fertilizer_trend_reasoning || "Stable data",
                icon: Activity,
                color: "text-purple-500",
                explanation: d.fertilizer_explanation,
            },
            {
                title: "Equipment Health",
                value: d.equipment_health || "N/A",
                unit: "%",
                trend: d.equipment_health_trend as any || "neutral",
                change: d.equipment_health_trend_reasoning || "Stable data",
                icon: BarChart3,
                color: "text-slate-500",
                explanation: d.equipment_health_explanation,
            },
            {
                title: "Solar Radiation",
                value: d.solar_radiation || "N/A",
                unit: "MJ/m²",
                trend: d.solar_radiation_trend as any || "neutral",
                change: d.solar_radiation_trend_reasoning || "Stable data",
                icon: Sun,
                color: "text-yellow-500",
                explanation: d.solar_radiation_explanation,
            },
            {
                title: "Harvest Progress",
                value: d.harvest_progress || "N/A",
                unit: "%",
                trend: d.harvest_progress_trend as any || "neutral",
                change: d.harvest_progress_trend_reasoning || "Stable data",
                icon: Trees,
                color: "text-emerald-600",
                explanation: d.harvest_progress_explanation,
            }
        ];
    }, [kpiData]);

    if (loading) {
        return <div className="p-8 flex items-center justify-center">Loading Dashboard Data...</div>;
    }

    return (
        <div className="p-4 md:p-8 space-y-6 md:space-y-8 bg-zinc-50 min-h-screen">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-gray-900">Agriculture Dashboard</h2>
                    <p className="text-muted-foreground mt-1">Real-time overview of your farm's health and metrics.</p>
                </div>
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 w-full md:w-auto">
                    <div className="flex items-center space-x-2 w-full sm:w-auto">
                        {kpiData?.is_stale && (
                            <div
                                onClick={recalculating ? undefined : handleRecalculate}
                                className={`flex items-center px-3 py-1.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200 cursor-pointer hover:bg-amber-200 transition-colors flex-1 sm:flex-initial ${recalculating ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                <span className="w-2 h-2 bg-amber-500 rounded-full mr-2 animate-pulse shrink-0"></span>
                                <span className="text-xs md:text-sm font-medium truncate">
                                    {recalculating ? "Recalculating..." : "New Data Available"}
                                </span>
                            </div>
                        )}
                        <button
                            onClick={recalculating ? undefined : handleRecalculate}
                            disabled={recalculating}
                            className={`p-2 rounded-md border border-gray-200 hover:bg-gray-100 transition-colors shrink-0 ${recalculating ? 'opacity-50 cursor-not-allowed' : ''}`}
                            title="Force Recalculate"
                        >
                            <Activity className={`h-4 w-4 text-gray-500 ${recalculating ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                    <span className="text-xs md:text-sm text-gray-500 shrink-0">
                        Updated: {kpiData?.last_updated ? new Date(kpiData.last_updated).toLocaleTimeString() : 'Never'}
                    </span>
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {kpis.map((kpi, index) => (
                    <KPICard key={kpi.title} {...kpi} delay={index * 0.05} />
                ))}
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4 hover:shadow-md transition-shadow">
                    <CardHeader>
                        <CardTitle>Crop Health Overview</CardTitle>
                    </CardHeader>
                    <CardContent className="pl-2">
                        <div className="h-[200px] flex items-center justify-center text-gray-400">
                            Graph Placeholder (Recharts)
                        </div>
                    </CardContent>
                </Card>
                <Card className="col-span-3 hover:shadow-md transition-shadow">
                    <CardHeader>
                        <CardTitle>Recent Alerts</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            <div className="flex items-center">
                                <span className="w-2 h-2 bg-red-500 rounded-full mr-2"></span>
                                <p className="text-sm font-medium">Pest outbreak risk in Sector 4</p>
                            </div>
                            <div className="flex items-center">
                                <span className="w-2 h-2 bg-yellow-500 rounded-full mr-2"></span>
                                <p className="text-sm font-medium">Soil moisture low in Sector 2</p>
                            </div>
                            <div className="flex items-center">
                                <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                                <p className="text-sm font-medium">Harvest scheduled for Sector 1</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div >
    );
};

// Fix for icon import
function CloudRainIcon(props: any) {
    return (
        <svg
            {...props}
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
        >
            <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
            <path d="M16 14v6" />
            <path d="M8 14v6" />
            <path d="M12 16v6" />
        </svg>
    )
}

export default Dashboard;
