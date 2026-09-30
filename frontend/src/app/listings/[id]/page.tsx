import type { Metadata } from "next";
import { DetailClient } from "@/components/detail/DetailClient";

export const metadata: Metadata = { title: "Property details" };

function safeDecode(v: string) {
  try {
    return decodeURIComponent(v);
  } catch {
    return v;
  }
}

export default async function ListingPage({ params }: PageProps<"/listings/[id]">) {
  const { id } = await params;
  return <DetailClient id={safeDecode(id)} />;
}
