export function formatMoney(amountInGrosze: number): string {
  if (!Number.isSafeInteger(amountInGrosze) || amountInGrosze < 0) {
    throw new RangeError("Kwota musi być nieujemną, bezpieczną liczbą groszy.");
  }

  const wholeZloty = Math.floor(amountInGrosze / 100);
  const grosze = amountInGrosze % 100;
  const formattedZloty = new Intl.NumberFormat("pl-PL", {
    maximumFractionDigits: 0,
  }).format(wholeZloty);

  return `${formattedZloty},${grosze.toString().padStart(2, "0")} zł`;
}
