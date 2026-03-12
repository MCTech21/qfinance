import React from "react";
import { Card, CardContent } from "./ui/card";

class DashboardSectionErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch() {
    // noop: avoid crashing full dashboard module on partial render errors
  }

  render() {
    if (this.state.hasError) {
      return (
        <Card>
          <CardContent className="pt-6 text-muted-foreground" data-testid="dashboard-section-error">
            Sin datos suficientes para calcular este indicador
          </CardContent>
        </Card>
      );
    }

    return this.props.children;
  }
}

export default DashboardSectionErrorBoundary;
