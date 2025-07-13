import React from 'react';
interface DocumentViewerProps {
  taskId: string;
}
export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  taskId
}) => {
  return <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border flex items-center justify-between bg-white">
        <div className="flex items-center">
          <div className="w-6 h-6 bg-blue-100 rounded flex items-center justify-center mr-2">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <div>
            <h2 className="font-medium text-sm">
              Updated Comprehensive Big Data Teaching Resources for
              Undergraduate Students
            </h2>
            <p className="text-xs text-muted-foreground">
              Last modified: 12:23 7/10
            </p>
          </div>
        </div>
        <div className="flex items-center">
          <button className="p-1 rounded-md hover:bg-accent">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-8 bg-white">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-3xl font-bold mb-6">
            Updated Comprehensive Big Data Teaching Resources for Undergraduate
            Students
          </h1>
          <h2 className="text-xl font-bold mt-8 mb-4">Introduction</h2>
          <p className="mb-4">
            This report provides an updated and comprehensive guide for
            educators planning to teach Big Data to undergraduate students. It
            incorporates a revised 14-week lesson plan, a curated list of the
            latest free and reputable books (published within the last three
            years), valuable tutorials, and practical lab session ideas. The aim
            is to equip students with both theoretical understanding and
            hands-on experience in the rapidly evolving field of Big Data.
          </p>
          <p className="mb-4">
            Big Data refers to datasets that are too large or complex to be
            dealt with by traditional data-processing application software. The
            challenges include capture, storage, analysis, data curation,
            search, sharing, transfer, visualization, querying, updating,
            information privacy and data source. The concept of Big Data is
            often characterized by the "3Vs": Volume, Velocity, and Variety,
            with additional Vs like Veracity and Value also being recognized as
            crucial aspects.
          </p>
          <p className="mb-4">
            This curriculum is designed to provide a solid foundation in Big
            Data concepts, technologies, and practical applications, preparing
            students for further studies or entry-level positions in
            data-intensive fields.
          </p>
          <h2 className="text-xl font-bold mt-8 mb-4">
            Free and Open-Source Big Data Books (2022-2025)
          </h2>
          <p className="mb-4">
            Access to quality educational materials is crucial for learning.
            Here is a selection of free and open-source Big Data and Data
            Science books suitable for undergraduate students, covering various
            aspects of data science and big data technologies, with publication
            dates within the last three years (2022-2025):
          </p>
          <ul className="list-disc pl-6 mb-6 space-y-2">
            <li>Veridical Data Science by Bin Yu & Rebecca L. Barter (2023)</li>
            <li>Hadoop: The Definitive Guide by Tom White (2022 Edition)</li>
            <li>Data Science from Scratch by Joel Grus (2023)</li>
            <li>
              Machine Learning Engineering with Python by Andrew P. McMahon
              (2022)
            </li>
            <li>
              Practical Statistics for Data Scientists by Peter Bruce & Andrew
              Bruce (2023)
            </li>
          </ul>
          <h2 className="text-xl font-bold mt-8 mb-4">
            14-Week Lesson Plan Overview
          </h2>
          <div className="border rounded-md overflow-hidden mb-6">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left">Week</th>
                  <th className="px-4 py-2 text-left">Topic</th>
                  <th className="px-4 py-2 text-left">Resources</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t">
                  <td className="px-4 py-2">Week 1</td>
                  <td className="px-4 py-2">Introduction to Big Data</td>
                  <td className="px-4 py-2">Veridical Data Science (Ch. 1)</td>
                </tr>
                <tr className="border-t bg-gray-50">
                  <td className="px-4 py-2">Week 2</td>
                  <td className="px-4 py-2">Data Storage Solutions</td>
                  <td className="px-4 py-2">Hadoop Guide (Ch. 2-3)</td>
                </tr>
                <tr className="border-t">
                  <td className="px-4 py-2">Week 3</td>
                  <td className="px-4 py-2">Data Processing Frameworks</td>
                  <td className="px-4 py-2">Lab: Spark Installation</td>
                </tr>
                <tr className="border-t bg-gray-50">
                  <td className="px-4 py-2">Week 4</td>
                  <td className="px-4 py-2">Distributed Computing</td>
                  <td className="px-4 py-2">Video Tutorials + Lab</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>;
};