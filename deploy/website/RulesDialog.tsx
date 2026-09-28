import { X } from "@phosphor-icons/react";
import { useEffect, useRef } from "react";

interface RulesDialogProps {
  open: boolean;
  onClose: () => void;
}

export function RulesDialog({ open, onClose }: RulesDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      className="rules-dialog"
      aria-labelledby="rules-dialog-title"
      onClose={onClose}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="dialog-heading">
        <h2 id="rules-dialog-title">游戏规则</h2>
        <button className="icon-button" type="button" onClick={onClose} aria-label="关闭规则">
          <X aria-hidden="true" />
        </button>
      </div>
      <div className="rules-content">
        <section>
          <h3>目标</h3>
          <p>白方让球从左边或右边离开棋盘，黑方让球从上边或下边离开棋盘。</p>
        </section>
        <section>
          <h3>桩与墙</h3>
          <p>桩放在方格交点。相邻的同色桩立即形成墙，球不能穿过墙。</p>
          <p>未参与墙的桩是浮桩，参与至少一段墙的桩是锚桩。</p>
        </section>
        <section>
          <h3>替换</h3>
          <p>可以用自己的桩替换对方浮桩，但替换后必须立刻与已有己方桩形成墙。锚桩不能替换。</p>
        </section>
        <section>
          <h3>球的移动</h3>
          <p>每次落桩后计算全部最短逃生路线。如果这些路线的第一步全部相同，球向该方向移动一格，否则不移动。</p>
          <p>等价地说：从球当前位置首步向四个方向逃生的总步数中，只有一个方向最短时，球才会向它移动。</p>
          <p>每回合最多移动一格，越过边界的一步计入路径长度。</p>
        </section>
        <section>
          <h3>胜负</h3>
          <p>球从左右边界离开时白方获胜，从上下边界离开时黑方获胜。落桩后完全封死球的一方立即获胜。</p>
          <p>轮到一方时没有任何合法落子或替换位置，游戏和棋。</p>
        </section>
        <section>
          <h3>辅助信息</h3>
          <p>简单模式在球的上、右、下、左标注从当前位置首步向该方向到任意出口的最少总步数（包含第一步和出界的一步）；预览尚未确认的落子时，数字会直接切换为落子后的值。</p>
          <p>被墙挡住、无法一步到达的方向显示 ∞，一步即可越界的方向显示 1；若最小值唯一，该数字会以强调色标出。所有提示都不参与胜负判定。</p>
        </section>
      </div>
      <button className="primary-button dialog-confirm" type="button" onClick={onClose}>
        知道了
      </button>
    </dialog>
  );
}
