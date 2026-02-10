import { cn } from "../lib/utils";

const TrafficLight = ({ status, percentage, showLabel = true, size = "default" }) => {
  const getStatusConfig = () => {
    switch (status) {
      case "green":
        return {
          bg: "bg-emerald-500/15",
          border: "border-emerald-500/30",
          text: "text-emerald-400",
          dot: "bg-emerald-500",
          label: "Normal"
        };
      case "yellow":
        return {
          bg: "bg-amber-500/15",
          border: "border-amber-500/30",
          text: "text-amber-400",
          dot: "bg-amber-500",
          label: "Alerta"
        };
      case "red":
        return {
          bg: "bg-red-500/15",
          border: "border-red-500/30",
          text: "text-red-400",
          dot: "bg-red-500",
          label: "Exceso"
        };
      default:
        return {
          bg: "bg-muted",
          border: "border-border",
          text: "text-muted-foreground",
          dot: "bg-muted-foreground",
          label: "N/A"
        };
    }
  };

  const config = getStatusConfig();
  
  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs",
    default: "px-2.5 py-1 text-sm",
    lg: "px-3 py-1.5 text-base"
  };

  const dotSizes = {
    sm: "h-1.5 w-1.5",
    default: "h-2 w-2",
    lg: "h-2.5 w-2.5"
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        config.bg,
        config.border,
        config.text,
        sizeClasses[size]
      )}
      data-testid={`traffic-light-${status}`}
    >
      <span className={cn("rounded-full", config.dot, dotSizes[size])} />
      {showLabel && (
        <span>
          {percentage !== undefined ? `${percentage.toFixed(1)}%` : config.label}
        </span>
      )}
    </span>
  );
};

export default TrafficLight;
