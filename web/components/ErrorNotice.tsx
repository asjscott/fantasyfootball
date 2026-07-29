export function ErrorNotice({ message }: { message: string }) {
  return (
    <div className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
      <p className="font-medium">Couldn&apos;t load data</p>
      <p className="mt-1 text-red-700">{message}</p>
    </div>
  );
}
