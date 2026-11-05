"use client";
import { JobForm } from "@/components/app/job-form";
import { PageHeader } from "@/components/ui/misc";

export default function NewJob() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="New job" description="Describe the role; AI extracts structured requirements you can edit." />
      <JobForm />
    </div>
  );
}
