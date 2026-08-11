import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'DRK Troisdorf Frühwarnsystem',
  description: 'Echtzeit-Lagebild und Frühwarnung für das DRK Troisdorf',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="de" className="dark">
      <head>
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          crossOrigin=""
        />
      </head>
      <body className="bg-dark-950 text-dark-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
