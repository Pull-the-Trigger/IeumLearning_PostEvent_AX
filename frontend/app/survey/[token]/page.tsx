import { SurveyForm } from "@/components/survey-form";
import { getSurveyDefinitionByToken } from "@/lib/survey-data";

export default async function PublicSurveyRoute({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const definition = getSurveyDefinitionByToken(token);
  if (!definition) return <main className="survey-shell"><div className="survey-error-page"><h1>설문 링크를 찾을 수 없습니다</h1><p>주소를 확인하거나 담당자에게 새 링크를 요청해 주세요.</p></div></main>;
  if (definition.status !== "open") return <main className="survey-shell"><div className="survey-error-page"><h1>종료된 설문입니다</h1><p>현재 응답을 받고 있지 않습니다.</p></div></main>;
  return <SurveyForm definition={definition} />;
}
