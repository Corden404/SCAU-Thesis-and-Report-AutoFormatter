::: {custom-style="SCAU_English_Title"}
Abstract
:::

::: {custom-style="SCAU_Abstract_En"}
With the rapid development of Internet technology, the acquisition and processing of massive data have become the core links in the fields of big data analysis, search engines, and artificial intelligence. Traditional single-machine crawlers often suffer from bottlenecks in bandwidth, memory, and computing resources when facing tens of millions or even hundreds of millions of web pages, making it difficult to complete efficient data collection in a short time. To solve this problem, this paper designs and implements a large-scale distributed Web crawler system based on Scrapy-Redis.

This paper first analyzes the core principles of distributed crawlers and compares the advantages and disadvantages of master-slave architecture and peer-to-peer architecture. Subsequently, using the Redis database as the distributed queue and deduplication center, combined with the efficient asynchronous processing capability of the Scrapy framework, a horizontally scalable crawler cluster was constructed. The system implements functions such as request scheduling and distribution, data deduplication, persistent storage, and exception retries. Experimental tests show that the system can significantly improve crawling efficiency when dealing with large-scale target websites and has good fault tolerance and load balancing capabilities. Finally, this paper cleans and performs preliminary analysis on the collected data, verifying the practical value of the system.
:::

::: {custom-style="SCAU_Keywords"}
[Key words:]{custom-style="SCAU_Keyword_Label"} Distributed Crawler; Scrapy-Redis; Data Collection; Redis; Load Balancing
:::
