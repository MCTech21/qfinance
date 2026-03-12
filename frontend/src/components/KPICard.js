import { cn } from "../lib/utils";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { safeCurrency, safeNumber, safePercent } from "../lib/numberFormatters";

const KPICard = ({ 
  title, 
  value, 
  subtitle, 
  trend, 
  trendValue, 
  icon: Icon, 
  variant = "default",
  className 
}) => {
  const getTrendIcon = () => {
    if (trend === "up") return <TrendingUp className="h-4 w-4" />;
    if (trend === "down") return <TrendingDown className="h-4 w-4" />;
    return <Minus className="h-4 w-4" />;
  };

  const getTrendColor = () => {
    if (variant === "inverse") {
      if (trend === "up") return "text-red-400";
      if (trend === "down") return "text-emerald-400";
    } else {
      if (trend === "up") return "text-emerald-400";
      if (trend === "down") return "text-red-400";
    }
    return "text-muted-foreground";
  };

  return (
    <div 
      className={cn("metric-card group", className)}
      data-testid={`kpi-card-${title?.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="flex items-start justify-between mb-3">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {title}
        </span>
        {Icon && (
          <div className="p-2 rounded-md bg-primary/10 text-primary group-hover:bg-primary/20 transition-colors">
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      
      <div className="space-y-1">
        <p className="text-2xl font-bold font-mono tabular-nums tracking-tight">
          {safeNumber(value) !== null ? safeCurrency(value, { fallback: "S/I" }) : (value ?? "S/I")}
        </p>
        
        {(subtitle || trendValue !== undefined) && (
          <div className="flex items-center gap-2">
            {trendValue !== undefined && (
              <span className={cn("flex items-center gap-1 text-xs font-medium", getTrendColor())}>
                {getTrendIcon()}
                {safeNumber(trendValue) !== null ? safePercent(trendValue, { fallback: "S/I", fractionDigits: 1 }) : (trendValue ?? "S/I")}
              </span>
            )}
            {subtitle && (
              <span className="text-xs text-muted-foreground">{subtitle}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default KPICard;
