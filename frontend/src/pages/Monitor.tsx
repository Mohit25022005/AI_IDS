import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Search } from "lucide-react";

const mockPackets = [
  { id: 1, timestamp: "2025-01-15 10:23:45", sourceIP: "192.168.1.45", destIP: "10.0.0.1", protocol: "TCP", prediction: "Normal", confidence: 0.94 },
  { id: 2, timestamp: "2025-01-15 10:23:46", sourceIP: "172.16.0.23", destIP: "10.0.0.1", protocol: "UDP", prediction: "Malicious", confidence: 0.87 },
  { id: 3, timestamp: "2025-01-15 10:23:47", sourceIP: "192.168.1.102", destIP: "10.0.0.1", protocol: "HTTP", prediction: "Normal", confidence: 0.96 },
  { id: 4, timestamp: "2025-01-15 10:23:48", sourceIP: "10.20.30.40", destIP: "10.0.0.1", protocol: "HTTPS", prediction: "Normal", confidence: 0.98 },
  { id: 5, timestamp: "2025-01-15 10:23:49", sourceIP: "203.0.113.15", destIP: "10.0.0.1", protocol: "TCP", prediction: "Malicious", confidence: 0.92 },
];

export default function Monitor() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  const filteredPackets = mockPackets.filter(packet => {
    const matchesSearch = packet.sourceIP.includes(search) || packet.destIP.includes(search);
    const matchesFilter = filter === "all" || packet.prediction.toLowerCase() === filter;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="space-y-6">
      <Card className="border-border bg-card/50 backdrop-blur-sm">
        <CardHeader>
          <CardTitle className="text-foreground">Live Network Monitor</CardTitle>
          <div className="flex flex-col md:flex-row gap-4 mt-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by IP address..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 bg-background/50"
              />
            </div>
            <Select value={filter} onValueChange={setFilter}>
              <SelectTrigger className="w-full md:w-48 bg-background/50">
                <SelectValue placeholder="Filter by prediction" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Packets</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="malicious">Malicious</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Timestamp</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Source IP</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Dest IP</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Protocol</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Prediction</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {filteredPackets.map((packet) => (
                  <tr key={packet.id} className="border-b border-border/50 hover:bg-secondary/30 transition-colors">
                    <td className="py-3 px-4 text-sm text-foreground">{packet.timestamp}</td>
                    <td className="py-3 px-4 text-sm font-mono text-primary">{packet.sourceIP}</td>
                    <td className="py-3 px-4 text-sm font-mono text-foreground">{packet.destIP}</td>
                    <td className="py-3 px-4 text-sm">
                      <Badge variant="outline">{packet.protocol}</Badge>
                    </td>
                    <td className="py-3 px-4 text-sm">
                      <Badge variant={packet.prediction === "Normal" ? "default" : "destructive"}>
                        {packet.prediction}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-sm text-foreground">{(packet.confidence * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
