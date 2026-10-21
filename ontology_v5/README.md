# Legal RAG Ontology V5

Ontology V5 là hợp đồng dữ liệu cho một hệ thống RAG pháp luật có cấu trúc. Nó giúp hệ thống không chỉ tìm đoạn văn giống câu hỏi, mà còn xác định:

- văn bản và điều khoản nào là nguồn;
- quy định cụ thể nói gì, áp dụng cho ai và trong điều kiện nào;
- quy định có hiệu lực tại thời điểm được hỏi hay không;
- có ngoại lệ, chế tài hoặc sửa đổi liên quan hay không;
- kết luận dựa trên đoạn trích nào;
- dữ liệu đã được review và bao phủ đến đâu.

V5 không phải một LLM, một cơ sở dữ liệu hoàn chỉnh hay một bộ luật đã được số hóa đầy đủ. Nó là lớp ngôn ngữ chung giữa quy trình trích xuất, graph database, retrieval, logic ứng dụng và LLM tạo câu trả lời.

## 1. Bức tranh tổng thể

```text
Nguồn pháp luật
    |
    v
Document -> Provision -> Chunk
    |           |
    |           +--------> Rule <--------> Entity
    |                         |
    |                         +----------> Rule ngoại lệ/chế tài
    |
    +---- thay đổi pháp lý --> Change -> Document/Provision/Rule

                         Graph dữ liệu
                              |
                              v
Câu hỏi -> nhận diện thời điểm/phạm vi -> tìm Rule -> mở rộng phụ thuộc
        -> đánh giá điều kiện/ngoại lệ -> lấy evidence -> LLM diễn đạt
```

Hệ thống có hai luồng chính:

1. **Ingestion:** chuyển văn bản nguồn thành dữ liệu graph có cấu trúc.
2. **Retrieval và trả lời:** dùng graph để chọn đúng Rule, thời gian, ngoại lệ và bằng chứng trước khi LLM diễn đạt câu trả lời.

LLM có thể hỗ trợ trích xuất và diễn đạt, nhưng không phải nguồn chân lý duy nhất. ID, hash, hiệu lực, quan hệ, phạm vi và bằng chứng phải được ứng dụng quản lý theo hợp đồng V5.

## 2. V5 giải quyết vấn đề gì?

RAG chỉ dựa trên tìm kiếm đoạn văn thường gặp các lỗi:

- tìm được câu giống ngữ nghĩa nhưng sai thời điểm hiệu lực;
- lấy nghĩa vụ chung mà bỏ sót ngoại lệ;
- tìm được chế tài nhưng không biết nó xử lý hành vi nào;
- trộn dữ kiện của nhiều người hoặc nhiều phương tiện;
- coi một đoạn không tìm thấy là bằng chứng rằng pháp luật không quy định;
- trả lời chắc chắn dù corpus chưa bao phủ văn bản sửa đổi;
- đưa ra trích dẫn nhưng không thể đối chiếu chính xác với nguồn.

V5 xử lý các vấn đề này bằng cách tách:

- cấu trúc tài liệu khỏi quy định pháp lý;
- hành vi khỏi lực quy phạm;
- điều kiện khỏi nội dung mô tả;
- hiệu lực pháp lý khỏi thời gian hệ thống ghi nhận;
- nguồn văn bản khỏi diễn giải được trích xuất;
- quan hệ có thể suy ra khỏi quan hệ cần bằng chứng.

## 3. Sáu loại node cốt lõi

V5 sử dụng sáu loại node lưu trữ. Số loại node ít là chủ ý chuẩn hóa, không phải giới hạn số khái niệm pháp luật có thể biểu diễn.

| Node | Vai trò trong hệ thống | Ví dụ |
|---|---|---|
| `Document` | Một nguồn hoặc ấn bản tài liệu xác định | Luật số 36/2024/QH15, bản PDF gốc |
| `Provision` | Đơn vị cấu trúc có địa chỉ trong văn bản | Chương II, Điều 10, Khoản 3 |
| `Chunk` | Đoạn văn bản nguồn bất biến dùng cho retrieval và citation | Nội dung Khoản 3 Điều 10 |
| `Rule` | Một phát biểu pháp lý nguyên tử | Cấm bố trí trẻ em ngồi cùng hàng ghế với người lái |
| `Entity` | Chủ thể hoặc khái niệm được tái sử dụng | Người lái xe, trẻ em, xe ô tô |
| `Change` | Một tác động pháp lý lên nội dung khác | Sửa đổi, thay thế, bãi bỏ, bắt đầu hiệu lực |

### Vì sao không giữ hàng chục loại node như V4?

V4 dùng lớp riêng cho nhiều khái niệm như người, phương tiện, hạ tầng và giấy tờ. V5 giữ cấu trúc lưu trữ ổn định:

- loại khái niệm nằm ở `Entity.kind`;
- phân loại hẹp–rộng dùng `IS_A`;
- vai trò trong từng quy định nằm ở `Rule.bindings`;
- hành vi nằm ở `Rule.action`;
- điều kiện nằm ở `Rule.condition`.

Nhờ đó, thêm một khái niệm pháp luật mới thường không đòi hỏi tạo một loại node database mới.

## 4. Rule là trung tâm ngữ nghĩa

`Rule` không phải toàn bộ Điều hoặc Khoản. Nó là một quy định đủ nhỏ để có:

- loại quy định riêng;
- lực quy phạm riêng;
- đối tượng và vai trò riêng;
- hành vi riêng;
- điều kiện riêng;
- khoảng hiệu lực riêng;
- bằng chứng riêng;
- ngoại lệ hoặc chế tài trỏ chính xác tới nó.

Ví dụ một Khoản có thể được tách thành:

1. Rule cấm một hành vi;
2. Rule bắt buộc sử dụng thiết bị;
3. Rule bắt buộc hướng dẫn sử dụng thiết bị;
4. Rule ngoại lệ cho một loại phương tiện.

### Các loại Rule

| `kind` | Mục đích |
|---|---|
| `norm` | Quy phạm chung |
| `definition` | Định nghĩa một khái niệm |
| `mandate` | Giao nhiệm vụ hoặc thẩm quyền |
| `sanction` | Chế tài |
| `exception` | Ngoại lệ làm mất áp dụng Rule khác |
| `transition` | Quy định chuyển tiếp |
| `procedure` | Trình tự hoặc thủ tục |

### Lực quy phạm

`modality` trả lời quy định đang:

- bắt buộc: `obligated`;
- cấm: `forbidden`;
- cho phép: `permitted`;
- hoặc không trực tiếp mang lực quy phạm: `none`.

`action` chỉ mô tả hành vi trung tính. Không nhúng ý nghĩa “cấm” hay “phải” vào tên action; ý nghĩa đó thuộc về `modality`.

### Binding và vai trò

`bindings` nối biến trong Rule với Entity và vai trò của Entity trong phát biểu:

```text
driver -> Người lái xe -> actor
child  -> Trẻ em       -> beneficiary
car    -> Xe ô tô      -> vehicle
```

Các vai trò hiện có gồm `actor`, `beneficiary`, `authority`, `vehicle`, `object`, `instrument`, `location` và `context`.

Binding giúp hệ thống không trộn dữ kiện của các đối tượng khác nhau khi đánh giá một tình huống.

### Điều kiện

Điều kiện dùng cây biểu thức:

- `all`: tất cả điều kiện con phải đúng;
- `any`: ít nhất một điều kiện con đúng;
- `not`: phủ định;
- `predicate`: so sánh một fact có kiểu và đơn vị;
- `text`: điều kiện chưa thể cấu trúc hóa an toàn.

Ví dụ:

```text
child.age_years < 10
AND child.height_m < 1.35 m
AND car.carrying_child = true
```

Ứng dụng nên dùng logic ba giá trị: `true`, `false`, `unknown`. Thiếu dữ kiện không được tự động coi là điều kiện đúng hoặc sai.

## 5. Mười ba loại quan hệ

### Quan hệ cấu trúc và quan hệ sinh từ trường chuẩn

| Quan hệ | Chiều |
|---|---|
| `CONTAINS` | Document/Provision → Provision |
| `HAS_CHUNK` | Provision → Chunk |
| `HAS_RULE` | Provision → Rule |
| `HAS_CHANGE` | Provision → Change |
| `ARGUMENT` | Rule → Entity |
| `DEFINES` | Rule định nghĩa → Entity được định nghĩa |

Các cạnh này phản chiếu trường chuẩn như `parent_id`, `provision_id` và `bindings`. Ứng dụng không nên coi cạnh và trường nguồn là hai khẳng định độc lập.

### Quan hệ ngữ nghĩa cần nguồn và audit

| Quan hệ | Chiều và ý nghĩa |
|---|---|
| `ISSUED_BY` | Document → tổ chức ban hành |
| `IS_A` | Entity hẹp → Entity rộng |
| `REFERENCES` | Document/Provision/Rule → nguồn được dẫn chiếu |
| `EXCEPTION_TO` | Rule ngoại lệ/thay thế → Rule bị tác động |
| `SANCTION_FOR` | Rule chế tài → Rule bị vi phạm |
| `REVISES` | Rule mới → Rule cũ |

### Quan hệ thay đổi

`TARGETS` nối một `Change` với Document, Provision hoặc Rule bị tác động. Change còn mô tả:

- loại tác động;
- ngày có hiệu lực;
- phạm vi chính xác hoặc cả cây con;
- đối tượng bị loại trừ;
- Rule chuyển tiếp liên quan.

Quan hệ trong V5 có hướng. Truy vấn chiều ngược không yêu cầu lưu thêm cạnh inverse.

## 6. Thời gian, phiên bản và lịch sử

V5 phân biệt hai câu hỏi:

1. **Nội dung có hiệu lực pháp lý khi nào?**  
   Dùng `valid_from`, `valid_to`, `effective_on`.

2. **Hệ thống biết bản ghi này khi nào?**  
   Dùng `recorded_from`, `recorded_to`.

Ví dụ một Rule có hiệu lực từ năm 2025 nhưng hệ thống chỉ thu thập được vào năm 2026. Hai mốc này không được nhập làm một.

Khoảng thời gian dùng quy ước nửa mở `[from, to)`. `null` thể hiện cận chưa biết hoặc chưa xác định theo ngữ cảnh trường, không mặc định là ngày hiện tại.

`rule_key` nhận diện cùng một quy định logic qua các phiên bản. `version` thể hiện phiên bản nội dung pháp lý. Sửa lỗi extraction không tự động tạo một phiên bản luật mới; nó thuộc lịch sử ghi nhận hệ thống.

## 7. Bằng chứng và mức độ tin cậy

Mỗi Rule, Change và quan hệ được khẳng định cần có evidence dẫn về một Chunk:

- `chunk_id`: đoạn nguồn;
- `start`, `end`: khoảng ký tự trong text;
- `quote`: trích đoạn phải khớp nguồn;
- `purpose`: bằng chứng cho nội dung, thời gian hoặc danh tính.

Ba mục đích evidence:

| `purpose` | Dùng cho |
|---|---|
| `content` | Nội dung của phát biểu pháp lý |
| `temporal` | Ngày hiệu lực hoặc khoảng thời gian |
| `identity` | Danh tính hoặc phân loại khái niệm |

`review_status` có thể là `pending_review`, `verified` hoặc `rejected`. Trạng thái verified chỉ nói snapshot đã được review theo quy trình; nó không tự chứng minh corpus đầy đủ hoặc kết luận pháp luật luôn đúng.

`confidence` là độ tin cậy của extraction, không phải xác suất một kết luận pháp lý đúng.

## 8. Các file trong thư mục

| File | Trách nhiệm |
|---|---|
| [`graph.schema.json`](graph.schema.json) | Hợp đồng JSON: loại node, trường, kiểu dữ liệu, enum và cấu trúc lồng |
| [`relation_catalog.json`](relation_catalog.json) | Danh mục cạnh: endpoint hợp lệ, role, trường bắt buộc và hierarchy |
| [`runtime_profile.json`](runtime_profile.json) | Cấu hình pilot: ngân sách ingestion/retrieval, ánh xạ Neo4j, fact/action catalog |
| [`example_original_law.json`](example_original_law.json) | Dataset minh họa cách các thành phần kết hợp |
| [`README.md`](README.md) | Tổng quan hệ thống và hướng dẫn đọc |

Thứ tự đọc khuyến nghị:

1. README này để hiểu kiến trúc;
2. `example_original_law.json` để thấy dữ liệu thực tế;
3. `graph.schema.json` khi cần tra trường cụ thể;
4. `relation_catalog.json` khi xây graph hoặc traversal;
5. `runtime_profile.json` khi xây ingestion, retrieval hoặc Neo4j.

## 9. Hợp đồng dataset

Một dataset trao đổi V5 có bốn phần:

```json
{
  "schema_version": "5.0",
  "dataset": {
    "id": "example.original_36_2024_QH15",
    "scope": "original_law_example",
    "coverage_note": "Phạm vi và giới hạn của tập dữ liệu"
  },
  "nodes": [],
  "edges": []
}
```

`dataset.scope` phân biệt:

- `original_law_example`: ví dụ từ bản luật gốc;
- `synthetic_test`: dữ liệu giả lập;
- `curated_corpus`: corpus được quản trị để sử dụng thực tế.

`coverage_note` phải nói rõ dữ liệu bao phủ và chưa bao phủ gì. Một dataset đúng schema không đồng nghĩa với corpus đầy đủ.

Chi tiết từng trường nằm trong `graph.schema.json`. README không lặp lại toàn bộ schema để tránh biến tài liệu nhập môn thành danh sách field dài.

## 10. Luồng ingestion

Một quy trình ingestion điển hình:

1. Thu thập nguồn, lưu URI, hash và thông tin phiên bản.
2. Tạo `Document` cho đúng ấn bản nguồn.
3. Phân tích cây cấu trúc thành các `Provision`.
4. Chuẩn hóa text một lần và tạo các `Chunk` bất biến.
5. Trích xuất các Rule nguyên tử, Entity, binding, action và condition.
6. Gắn evidence chính xác về Chunk.
7. Nhận diện định nghĩa, ngoại lệ, chế tài, dẫn chiếu và thay đổi.
8. Sinh các cạnh cấu trúc từ trường nguồn chuẩn.
9. Kiểm tra tham chiếu, hierarchy, hash, thời gian, chu kỳ và tính nhất quán.
10. Đưa các diễn giải chưa chắc chắn vào review thay vì âm thầm coi là đúng.
11. Ghi graph theo transaction và giữ lịch sử snapshot.

LLM có thể thực hiện bước đề xuất extraction, nhưng ứng dụng phải kiểm soát vocabulary, ID, hash, reference, interval và trạng thái review.

## 11. Luồng retrieval và trả lời

Một yêu cầu RAG nên cung cấp:

- `legal_as_of`: hỏi pháp luật có hiệu lực tại ngày nào;
- `known_at`: chỉ dùng thông tin hệ thống đã biết tại thời điểm nào;
- `jurisdiction`;
- `interpretation_scope`;
- dữ kiện của tình huống và binding tương ứng.

Luồng xử lý đề xuất:

1. Xác định thời gian, phạm vi và đối tượng của câu hỏi.
2. Tìm ứng viên bằng lexical và vector retrieval trên Chunk/Rule.
3. Lọc Rule theo hiệu lực pháp lý và snapshot hệ thống.
4. Mở rộng graph có giới hạn.
5. Lấy ngoại lệ, chế tài và dependency liên quan.
6. Đánh giá condition bằng fact có kiểu; giữ kết quả `unknown` khi thiếu dữ kiện.
7. Không kết luận chắc chắn nếu dependency hoặc coverage chưa hoàn tất.
8. Rerank và đưa Rule cùng evidence vào context.
9. Để LLM diễn đạt câu trả lời, ngày áp dụng, dữ kiện còn thiếu và citation.

Không nên đưa toàn bộ schema và graph vào mỗi prompt. Schema dùng để quản lý dữ liệu; prompt trả lời chỉ cần các Rule, dependency và evidence đã được chọn.

## 12. Runtime profile

`runtime_profile.json` là cấu hình pilot, không phải giới hạn phổ quát.

### Ingestion

Đặt giới hạn cho:

- độ sâu và kích thước condition;
- số node/cạnh mỗi batch;
- số Rule trên một Provision trước khi cần review;
- fan-out của quan hệ asserted;
- chính sách khi vượt giới hạn.

Vượt giới hạn phải được báo cáo hoặc cách ly để review, không được cắt mất điều kiện hay tạo Rule tổng hợp không có nguồn.

### Retrieval

Định nghĩa:

- số ứng viên lexical/vector/rerank;
- số seed Rule;
- số hop taxonomy/reference;
- số node/cạnh graph tối đa;
- dependency cần hoàn tất;
- timeout và context-token budget;
- metadata bắt buộc trong request/response.

Các con số hiện tại là điểm khởi đầu để benchmark, không phải năng lực đã được chứng minh.

### Fact catalog

Fact catalog quy định tên fact, kiểu, đơn vị và loại Entity được phép dùng trong condition. Ví dụ:

- `age_years`: number, đơn vị year;
- `height_m`: number, đơn vị m;
- `seat_rows`: integer, đơn vị count;
- `carrying_child`: boolean.

Fact chưa đăng ký không nên được LLM tự tạo rồi coi là hợp lệ.

### Action catalog

Action catalog quy định predicate và các slot/role. Ví dụ `use_child_restraint` có các slot actor, child, device và vehicle.

Khi mở rộng catalog cần xác định:

- tên predicate ổn định;
- slot bắt buộc;
- role của từng slot;
- kiểu Entity phù hợp;
- cách ánh xạ từ ngôn ngữ pháp luật.

### Neo4j

Profile mô tả:

- label và constraint ID;
- index khởi điểm;
- trường JSON cần serialize;
- thuộc tính cache được phép promote;
- cách lưu ngày và embedding;
- nguyên tắc tạo danh tính cạnh;
- yêu cầu transaction và locking.

Neo4j chỉ là một đích triển khai được đề xuất. Mô hình trao đổi JSON không bắt buộc hệ thống phải dùng Neo4j.

## 13. Dataset ví dụ

`example_original_law.json` minh họa một phần Khoản 3 Điều 10 và căn cứ hiệu lực tại Điều 88 của Luật 36/2024/QH15.

Nó hiện có:

- 1 Document;
- 6 Provision;
- 2 Chunk;
- 4 Entity;
- 4 Rule;
- 25 cạnh.

Bốn Rule minh họa:

1. cấm bố trí trẻ thuộc điều kiện cùng hàng ghế với người lái;
2. nghĩa vụ sử dụng thiết bị an toàn;
3. nghĩa vụ hướng dẫn sử dụng thiết bị;
4. ngoại lệ đối với xe chỉ có một hàng ghế.

Fixture cho thấy một câu luật có thể cần tách thành nhiều Rule và ngoại lệ phải trỏ đúng Rule bị tác động.

Đây chỉ là ví dụ từ bản luật gốc:

- không phải toàn bộ Luật 36/2024/QH15;
- không chứng minh đã bao phủ mọi sửa đổi;
- không phải corpus pháp luật hiện hành hoàn chỉnh;
- các diễn giải vẫn ở trạng thái `pending_review`.

## 14. Những ràng buộc ứng dụng phải thực hiện

JSON Schema chủ yếu kiểm tra hình dạng từng object. Importer hoặc tầng dịch vụ phải kiểm tra thêm:

- ID node/cạnh không trùng;
- reference trỏ tới node tồn tại và đúng loại;
- hierarchy Provision hợp lệ và không có chu kỳ;
- hash Chunk khớp text;
- quote khớp chính xác offset;
- cạnh derived khớp trường nguồn;
- action slot khớp binding và action catalog;
- fact, kiểu và unit khớp fact catalog;
- Rule definition, mandate, sanction và exception đủ thành phần;
- khoảng hiệu lực và khoảng ghi nhận hợp lệ, không chồng trái phép;
- taxonomy cùng kind, có scope và không có chu kỳ;
- Change có target, exclusion và transition hợp lệ;
- `REVISES` khớp Change, version và ngày hiệu lực;
- ngoại lệ/chế tài ánh xạ đúng biến của cùng tình huống;
- giới hạn ingestion/retrieval không bị vượt âm thầm.

Các kiểm tra kỹ thuật không thay thế review pháp lý.

## 15. Mở rộng V5

### Thêm một văn bản hoặc corpus

Không cần sửa schema. Tạo Document, Provision, Chunk, Rule, Entity, Change và các cạnh tương ứng trong dataset mới.

### Thêm fact hoặc action

Cập nhật `runtime_profile.json` sau khi xác định rõ kiểu, đơn vị, slot và role. Nội dung chưa hiểu nên giữ dạng text/pending review thay vì thêm predicate tùy tiện.

### Thêm một loại Entity

Nếu nhóm khái niệm đã nằm trong enum `Entity.kind`, chỉ cần thêm Entity dữ liệu. Nếu cần một kind hoàn toàn mới, phải thay đổi schema và đánh giá ảnh hưởng tới catalog, retrieval và storage.

### Thêm một loại quan hệ

Phải cập nhật đồng bộ:

- enum cạnh trong `graph.schema.json`;
- endpoint, role và trường trong `relation_catalog.json`;
- logic importer và traversal;
- quy tắc evidence, thời gian và cycle;
- tài liệu này nếu quan hệ thuộc kiến trúc cốt lõi.

Không nên tạo loại cạnh mới chỉ vì một thuật ngữ xuất hiện trong văn bản. Trước tiên xem nó có thể biểu diễn bằng Rule, binding, action, condition hoặc role hiện có không.

## 16. Khác biệt chính so với V4

| V4 | V5 |
|---|---|
| Một file lớn chứa lớp, quan hệ, temporal và cấu hình | Tách schema, relation catalog, runtime profile và dữ liệu ví dụ |
| Nhiều loại node miền | Sáu loại node lưu trữ ổn định |
| Hành vi và điều kiện thường là node/mô tả | Action và condition có cấu trúc |
| Ngoại lệ/chế tài tương đối tổng quát | Trỏ chính xác tới Rule bị tác động |
| Một trục thời gian chính | Tách legal time và recorded time |
| Evidence đơn giản | Evidence có chunk, offset, quote và purpose |
| Nhiều quy tắc kiểm tra ở dạng văn bản | Hợp đồng dữ liệu chi tiết hơn, nhưng ứng dụng vẫn phải thực thi kiểm tra liên bản ghi |

V5 mạnh hơn về khả năng biểu diễn và quản trị. Điều đó không tự động có nghĩa dataset V5 đang bao phủ nhiều văn bản hơn; độ phủ phụ thuộc vào corpus thực tế.

## 17. Giới hạn và trạng thái hiện tại

V5 hiện là thiết kế/pilot, chưa phải hệ thống production hoàn chỉnh.

Chưa được chứng minh đầy đủ:

- độ phủ toàn bộ luật và văn bản sửa đổi;
- độ đúng pháp lý của mọi Rule extraction;
- giải quyết mọi xung đột pháp luật;
- tự động nhận diện split/merge Rule;
- importer database và cơ chế concurrent update;
- hiệu năng graph, ANN recall và context cost trên corpus lớn;
- chất lượng câu trả lời trên gold set pháp lý;
- quy trình review và quản trị coverage ở quy mô production.

Không được dùng việc “không tìm thấy Rule” để kết luận “pháp luật không quy định” nếu chưa chứng minh corpus và dependency đầy đủ.

## 18. Hướng dẫn theo vai trò người đọc

### Người mới tìm hiểu hệ thống

Đọc các mục 1–8, sau đó mở `example_original_law.json`.

### Người xây pipeline extraction

Đọc các mục 3–7, 9–10, 12, 14 và `graph.schema.json`.

### Người xây graph/importer

Đọc mục 5–7, 9, 12, 14 cùng `relation_catalog.json` và phần Neo4j trong runtime profile.

### Người xây RAG

Đọc mục 4, 6–7, 11–12 và các budget trong `runtime_profile.json`.

### Chuyên gia pháp lý hoặc người review

Tập trung vào Rule summary, kind, modality, bindings, condition, thời gian, dependency và evidence trong dataset.

## 19. Thuật ngữ ngắn

| Thuật ngữ | Nghĩa |
|---|---|
| Canonical data | Dữ liệu theo đúng hợp đồng trao đổi V5 |
| Corpus coverage | Phạm vi nguồn và thay đổi mà hệ thống đã thu thập/đối chiếu |
| Dependency | Rule liên quan có thể làm thay đổi kết luận, như ngoại lệ hoặc chế tài |
| Derived edge | Cạnh được sinh từ trường nguồn chuẩn |
| Asserted edge | Cạnh là một khẳng định cần evidence và audit |
| Legal time | Thời gian nội dung có hiệu lực pháp lý |
| Recorded time | Thời gian hệ thống biết một snapshot |
| Interpretation scope | Phạm vi diễn giải/corpus mà Rule thuộc về |
| Binding | Ánh xạ biến của Rule tới Entity và vai trò |
| Predicate | Tên chuẩn của action hoặc fact có thể xử lý bằng máy |

## 20. Nguyên tắc cuối cùng

- Dùng ontology để kiểm soát dữ liệu, không chỉ đưa toàn bộ file cho LLM đọc.
- Giữ Chunk bất biến để citation và offset có thể kiểm chứng.
- Tách Rule đủ nhỏ để ngoại lệ, chế tài và hiệu lực trỏ chính xác.
- Không để LLM tự phát minh action, fact, ngày hiệu lực hoặc quan hệ.
- Giữ `unknown` khi thiếu dữ kiện.
- Luôn nêu phạm vi coverage và thời điểm áp dụng trong câu trả lời pháp luật.
- Schema đúng không đồng nghĩa diễn giải pháp luật đúng.
- Khi có mâu thuẫn, ưu tiên:
  1. `graph.schema.json` cho cấu trúc dữ liệu;
  2. `relation_catalog.json` cho quan hệ;
  3. `runtime_profile.json` cho catalog và giới hạn vận hành.
