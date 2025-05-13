import React from 'react';
import ReactMarkdown, { Components } from "react-markdown";
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import { Check, Copy, Download, Loader2 } from 'lucide-react';
import { GlassStyle, AnimationStyle } from '../types';

interface ResearchReportProps {
  output: {
    summary: string;
    details: {
      report: string;
    };
  } | null;
  isResetting: boolean;
  glassStyle: GlassStyle;
  fadeInAnimation: AnimationStyle;
  loaderColor: string;
  isGeneratingPdf: boolean;
  isCopied: boolean;
  onCopyToClipboard: () => void;
  onGeneratePdf: () => void;
}

const ResearchReport: React.FC<ResearchReportProps> = ({
  output,
  isResetting,
  glassStyle,
  fadeInAnimation,
  loaderColor,
  isGeneratingPdf,
  isCopied,
  onCopyToClipboard,
  onGeneratePdf
}) => {
  if (!output || !output.details) return null;

  // 自定义渲染器配置
  const components: Components = {
    div: ({node, ...props}) => {
      const id = props.id as string;
      if (id?.startsWith('footnote-')) {
        const refNum = id.replace('footnote-', '');
        return (
          <div 
            id={id} 
            className="text-gray-600 text-sm mt-2 mb-4 pl-4 border-l-2 border-gray-200"
            {...props}
          />
        );
      }
      return <div className="space-y-4 text-gray-800" {...props} />;
    },
    
    text: ({node, ...props}) => {
      const text = String(props.children);
      // 匹配引用标记 [^n] 或 [^n,n]
      const footnoteRegex = /\[\^(\d+(?:,\d+)*)\]/g;
      
      if (!footnoteRegex.test(text)) {
        return <>{props.children}</>;
      }
      
      const parts = text.split(footnoteRegex);
      const matches = text.match(footnoteRegex) || [];
      
      // 从参考文献部分提取URL映射
      const refUrlMap = new Map();
      // 修改：只获取最后一个 References 部分
      const refSections = output?.details?.report?.split('## References\n\n');
      if (refSections && refSections.length > 1) {
        const lastRefSection = refSections[refSections.length - 1];
        const refLines = lastRefSection.split('\n');
        for (const line of refLines) {
          // 修改正则表达式以匹配正确的引用格式
          const match = line.match(/\[\^(\d+)\]:\s*\[(.*?)\]\((https?:\/\/[^)]+)\)/);
          if (match) {
            const [, refNum, , url] = match;
            if (url.startsWith('http://') || url.startsWith('https://')) {
              refUrlMap.set(refNum, url);
            }
          }
        }
      }
      
      return (
        <>
          {parts.map((part, i) => (
            <React.Fragment key={i}>
              {part}
              {matches[i] && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const refNums = matches[i].slice(2, -1).split(',');
                    const firstRefNum = refNums[0];
                    const url = refUrlMap.get(firstRefNum);
                    
                    if (url && (url.startsWith('http://') || url.startsWith('https://'))) {
                      // 直接打开外部链接
                      window.open(url, '_blank', 'noopener,noreferrer');
                    } else {
                      // 如果找不到URL，滚动到对应的参考文献
                      const refId = `footnote-${firstRefNum}`;
                      const refElement = document.getElementById(refId);
                      if (refElement) {
                        refElement.scrollIntoView({ behavior: 'smooth' });
                      } else {
                        // 如果找不到具体的参考文献，滚动到参考文献部分
                        const referencesSection = document.querySelector('h2:contains("References")');
                        if (referencesSection) {
                          referencesSection.scrollIntoView({ behavior: 'smooth' });
                        }
                      }
                    }
                  }}
                  className="text-[#468BFF] hover:text-[#8FBCFA] no-underline font-medium mx-0.5 px-1 py-0.5 rounded bg-blue-50 hover:bg-blue-100 cursor-pointer transition-colors inline-block text-sm border-0 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50"
                  title={matches[i].slice(2, -1).split(',').map(refNum => {
                    const url = refUrlMap.get(refNum);
                    return url ? `[${refNum}]: ${url}` : null;
                  }).filter(Boolean).join('\n')}
                >
                  <sup>{matches[i].slice(2, -1)}</sup>
                </button>
              )}
            </React.Fragment>
          ))}
        </>
      );
    },
    
    h1: ({node, ...props}) => {
      const text = String(props.children);
      const isFirstH1 = text.includes("Research Report");
      const isReferences = text.includes("References");
      
      // 如果是 References 标题，检查是否是最后一个
      if (isReferences) {
        const refSections = output?.details?.report?.split('## References\n\n');
        if (refSections && refSections.length > 1) {
          // 如果不是最后一个 References 部分，不渲染
          const currentIndex = output?.details?.report?.indexOf(text);
          const lastRefIndex = output?.details?.report?.lastIndexOf('## References\n\n');
          if (currentIndex !== lastRefIndex) {
            return null;
          }
        }
      }
      
      return (
        <div>
          <h1 
            className={`font-bold text-gray-900 break-words whitespace-pre-wrap ${isFirstH1 ? 'text-5xl mb-10 mt-4 max-w-[calc(100%-8rem)]' : 'text-3xl mb-6'}`} 
            {...props} 
          />
          {isReferences && (
            <div className="h-[1px] w-full bg-gradient-to-r from-transparent via-gray-300 to-transparent my-8"></div>
          )}
        </div>
      );
    },
    
    h2: ({node, ...props}) => (
      <h2 className="text-3xl font-bold text-gray-900 first:mt-2 mt-8 mb-4" {...props} />
    ),
    
    h3: ({node, ...props}) => (
      <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3" {...props} />
    ),
    
    p: ({node, ...props}) => {
      const text = String(props.children);
      // 检查是否是脚注行
      const footnoteMatch = text.match(/^\[\^(\d+)\]:\s*(.*)/);
      if (footnoteMatch) {
        const [, refNum, content] = footnoteMatch;
        // 提取链接文本和URL
        const linkMatch = content.match(/\[(.*?)\]\((https?:\/\/[^)]+)\)/);
        if (linkMatch) {
          const [, linkText, url] = linkMatch;
          return (
            <p 
              id={`footnote-${refNum}`}
              className="text-gray-600 text-sm mt-2 mb-4 pl-4 border-l-2 border-gray-200"
            >
              <sup className="text-[#468BFF] font-medium mr-1">[{refNum}]</sup>
              <a 
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#468BFF] hover:text-[#8FBCFA] underline decoration-[#468BFF] hover:decoration-[#8FBCFA]"
              >
                {linkText}
              </a>
            </p>
          );
        }
      }
      return <p className="my-4" {...props} />;
    },
    
    ul: ({node, ...props}) => (
      <ul className="text-gray-800 space-y-1 list-disc pl-6" {...props} />
    ),
    
    li: ({node, ...props}) => (
      <li className="text-gray-800" {...props} />
    ),
    
    a: ({node, ...props}) => {
      const isFootnote = /^\[\^/.test(String(props.children));
      if (isFootnote) {
        return null; // 不渲染引用标记链接
      }

      const isReferenceLink = props.href && props.href.startsWith('http');
      if (isReferenceLink) {
        return (
          <a 
            {...props}
            className="text-[#468BFF] hover:text-[#8FBCFA] underline decoration-[#468BFF] hover:decoration-[#8FBCFA] cursor-pointer transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          />
        );
      }

      return (
        <a 
          {...props}
          className="text-[#468BFF] hover:text-[#8FBCFA] underline decoration-[#468BFF] hover:decoration-[#8FBCFA] cursor-pointer transition-colors"
          target="_blank"
          rel="noopener noreferrer"
        />
      );
    },
  };

  return (
    <div 
      className={`${glassStyle.card} ${fadeInAnimation.fadeIn} ${isResetting ? 'opacity-0 transform -translate-y-4' : 'opacity-100 transform translate-y-0'} font-['DM_Sans']`}
    >
      <div className="flex justify-end gap-2 mb-4">
        {output?.details?.report && (
          <>
            <button
              onClick={onCopyToClipboard}
              className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-[#468BFF] text-white hover:bg-[#8FBCFA] transition-all duration-200"
            >
              {isCopied ? (
                <Check className="h-5 w-5" />
              ) : (
                <Copy className="h-5 w-5" />
              )}
            </button>
            <button
              onClick={onGeneratePdf}
              disabled={isGeneratingPdf}
              className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-[#FFB800] text-white hover:bg-[#FFA800] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGeneratingPdf ? (
                <>
                  <Loader2 className="animate-spin h-5 w-5 mr-2" style={{ stroke: loaderColor }} />
                  Generating PDF...
                </>
              ) : (
                <>
                  <Download className="h-5 w-5" />
                  <span className="ml-2">PDF</span>
                </>
              )}
            </button>
          </>
        )}
      </div>
      <div className="prose prose-invert prose-lg max-w-none">
        <div className="mt-4">
          <ReactMarkdown
            rehypePlugins={[rehypeRaw]}
            remarkPlugins={[remarkGfm]}
            components={components}
          >
            {output.details.report || "No report available"}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
};

export default ResearchReport; 