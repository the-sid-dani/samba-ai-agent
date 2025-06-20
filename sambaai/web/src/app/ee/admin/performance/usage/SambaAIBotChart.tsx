import { ThreeDotsLoader } from "@/components/Loading";
import { getDatesList, useSambaAIBotAnalytics } from "../lib";
import { DateRangePickerValue } from "@/components/dateRangeSelectors/AdminDateRangeSelector";
import Text from "@/components/ui/text";
import Title from "@/components/ui/title";
import CardSection from "@/components/admin/CardSection";
import { AreaChartDisplay } from "@/components/ui/areaChart";

export function SambaAIBotChart({
  timeRange,
}: {
  timeRange: DateRangePickerValue;
}) {
  const {
    data: sambaaiBotAnalyticsData,
    isLoading: isSambaAIBotAnalyticsLoading,
    error: sambaaiBotAnalyticsError,
  } = useSambaAIBotAnalytics(timeRange);

  let chart;
  if (isSambaAIBotAnalyticsLoading) {
    chart = (
      <div className="h-80 flex flex-col">
        <ThreeDotsLoader />
      </div>
    );
  } else if (
    !sambaaiBotAnalyticsData ||
    sambaaiBotAnalyticsData[0] == undefined ||
    sambaaiBotAnalyticsError
  ) {
    chart = (
      <div className="h-80 text-red-600 text-bold flex flex-col">
        <p className="m-auto">Failed to fetch feedback data...</p>
      </div>
    );
  } else {
    const initialDate =
      timeRange.from || new Date(sambaaiBotAnalyticsData[0].date);
    const dateRange = getDatesList(initialDate);

    const dateToSambaAIBotAnalytics = new Map(
      sambaaiBotAnalyticsData.map((sambaaiBotAnalyticsEntry) => [
        sambaaiBotAnalyticsEntry.date,
        sambaaiBotAnalyticsEntry,
      ])
    );

    chart = (
      <AreaChartDisplay
        className="mt-4"
        data={dateRange.map((dateStr) => {
          const sambaaiBotAnalyticsForDate = dateToSambaAIBotAnalytics.get(dateStr);
          return {
            Day: dateStr,
            "Total Queries": sambaaiBotAnalyticsForDate?.total_queries || 0,
            "Automatically Resolved":
              sambaaiBotAnalyticsForDate?.auto_resolved || 0,
          };
        })}
        categories={["Total Queries", "Automatically Resolved"]}
        index="Day"
        colors={["indigo", "fuchsia"]}
        yAxisWidth={60}
      />
    );
  }

  return (
    <CardSection className="mt-8">
      <Title>Slack Channel</Title>
      <Text>Total Queries vs Auto Resolved</Text>
      {chart}
    </CardSection>
  );
}
