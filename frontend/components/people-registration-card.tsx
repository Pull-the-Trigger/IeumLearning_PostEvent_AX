"use client";

import { useRef, useState, type ReactNode } from "react";
import { Info, Upload } from "lucide-react";

type UploadSchemaKey = "participation" | "surveys" | "interactions";
type CardDefinition = { key: UploadSchemaKey; title: string; description: string; action?: ReactNode };

type PeopleRegistrationCardProps = {
  onSchema: (key: UploadSchemaKey) => void;
  onHistory: () => void;
  onFiles: (key: UploadSchemaKey, files: File[]) => void;
  onParticipant: () => void;
  onInteraction: () => void;
};

function RegistrationUploadZone({
  card,
  onFiles,
}: {
  card: CardDefinition;
  onFiles: (key: UploadSchemaKey, files: File[]) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const openFilePicker = () => inputRef.current?.click();

  return (
    <div
      className={`registration-dropzone${dragging ? " dragging" : ""}`}
      role="button"
      tabIndex={0}
      onClick={openFilePicker}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openFilePicker();
        }
      }}
      onDragEnter={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragging(false);
        onFiles(card.key, [...event.dataTransfer.files]);
      }}
    >
      <Upload size={20} aria-hidden="true" />
      <span>파일 선택 또는 끌어다 놓기</span>
      <em>엑셀 파일 (.xlsx)</em>
      <input
        ref={(node) => {
          inputRef.current = node;
        }}
        type="file"
        multiple
        accept=".xlsx,.xls,.csv"
        aria-label={`${card.title} 파일 선택`}
        onChange={(event) => onFiles(card.key, [...(event.target.files ?? [])])}
      />
    </div>
  );
}

export function PeopleRegistrationCard({
  onSchema,
  onHistory,
  onFiles,
  onParticipant,
  onInteraction,
}: PeopleRegistrationCardProps) {
  const cards: CardDefinition[] = [
    {
      key: "participation",
      title: "참가자 명단",
      description: "행사별 참가자 명단 등록",
      action: (
        <button className="text-button" type="button" onClick={onParticipant}>
          참가자 직접 등록
        </button>
      ),
    },
    {
      key: "surveys",
      title: "만족도 설문",
      description: "외부 설문 응답 등록",
      action: <small className="form-help">온라인 설문 응답 자동 수집</small>,
    },
    {
      key: "interactions",
      title: "후속 연락 기록",
      description: "기존 고객 연락 기록 등록",
      action: (
        <button className="text-button" type="button" onClick={onInteraction}>
          연락 기록 직접 등록
        </button>
      ),
    },
  ];

  return (
    <section className="mail-card data-registration-card">
      <div className="card-heading">
        <div>
          <span className="card-kicker">01</span>
          <h2>고객 데이터 등록</h2>
        </div>
        <div className="data-management-actions">
          <button className="secondary-button" type="button" onClick={onHistory}>
            등록 이력
          </button>
        </div>
      </div>
      <div className="registration-grid">
        {cards.map((card) => (
          <div className="registration-card" key={card.key}>
            <div className="registration-card-heading">
              <strong>{card.title}</strong>
            </div>
            <small>{card.description}</small>
            <RegistrationUploadZone
              card={card}
              onFiles={onFiles}
            />
            <div className="registration-card-actions">
              <button className="secondary-button compact-button" type="button" onClick={() => onSchema(card.key)}>
                <Info size={13} /> 입력 양식 안내
              </button>
              {card.action}
            </div>
          </div>
        ))}
      </div>
      <p className="form-help registration-common-note">
        파일의 컬럼 구조를 검증한 후 등록합니다. 실제 통합 저장 기능은 아직 연동되지 않았습니다.
      </p>
    </section>
  );
}
